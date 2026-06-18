"""Router de exportação — arquivos para download.

Prefixo: /api/export

Endpoint:
  GET /api/export/bm/{ano}/{mes}/excel
    → Retorna .xlsx corporativo do BM mensal

Invariantes:
  • NÃO recalcula regras financeiras — usa montar_bm_completo() como está.
  • NÃO altera nenhum dado do banco — somente leitura.
  • Compatível com o BM em qualquer status (prévia, análise, fechado, consolidado).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import BmCiclo
from ..services import bm_service as svc
from ..services.export_service import gerar_excel_bm

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/export", tags=["export"])


@router.get(
    "/bm/{ano}/{mes}/excel",
    summary="Exportar BM mensal para Excel",
    description=(
        "Gera um arquivo .xlsx corporativo do Boletim de Medição (BM) do mês especificado. "
        "O Excel contém 5 abas: Resumo Executivo, Medição Mensal, Pendências, Curva S/EVM e Auditoria. "
        "Reflete exatamente os dados da tela — não recalcula nenhuma regra financeira."
    ),
    response_class=Response,
    responses={
        200: {
            "content": {
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}
            },
            "description": "Arquivo Excel do BM mensal",
        },
        404: {"description": "BM não encontrado para o mês informado"},
    },
)
def exportar_bm_excel(
    ano: int,
    mes: int,
    usuario: str = Query(default="sistema", description="Identificação do solicitante (para auditoria)"),
    db: Session = Depends(get_db),
) -> Response:
    """Exporta o BM do mês {ano}/{mes} como arquivo Excel profissional.

    Parâmetros:
    - **ano**: Ano do ciclo (ex: 2026)
    - **mes**: Mês do ciclo 1–12 (ex: 6)
    - **usuario**: Nome/login do solicitante — gravado na aba Auditoria

    Retorna:
        StreamingResponse com o arquivo BM_{ano}_{mes:02d}.xlsx para download.
    """
    # ── Validação básica ─────────────────────────────────────────────────────
    if not (1 <= mes <= 12):
        raise HTTPException(status_code=422, detail="Mês inválido. Use 1–12.")
    if not (2000 <= ano <= 2100):
        raise HTTPException(status_code=422, detail="Ano inválido.")

    # ── Localiza o ciclo ─────────────────────────────────────────────────────
    ciclo = (
        db.query(BmCiclo)
        .filter(BmCiclo.ano == ano, BmCiclo.mes == mes)
        .first()
    )
    if not ciclo:
        raise HTTPException(
            status_code=404,
            detail=(
                f"BM {ano}/{mes:02d} não encontrado. "
                "Verifique se o BM foi aberto para este período via POST /api/bm/abrir."
            ),
        )

    # ── Monta dados (fonte única — sem recalcular regras) ────────────────────
    try:
        bm_data = svc.montar_bm_completo(db, ciclo.id)
        curva_s = svc.get_curva_s_consolidada(db)
    except ValueError as exc:
        logger.error("Erro ao montar dados para exportação BM %d/%02d: %s", ano, mes, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Erro inesperado ao montar BM %d/%02d para exportação", ano, mes)
        raise HTTPException(
            status_code=500,
            detail="Erro interno ao montar dados do BM. Verifique os logs do servidor.",
        ) from exc

    # ── Gera o Excel ─────────────────────────────────────────────────────────
    try:
        xlsx_bytes = gerar_excel_bm(bm_data, curva_s, usuario=usuario)
    except Exception as exc:
        logger.exception("Erro ao gerar Excel para BM %d/%02d", ano, mes)
        raise HTTPException(
            status_code=500,
            detail="Erro interno ao gerar o arquivo Excel. Verifique os logs do servidor.",
        ) from exc

    filename = f"BM_{ano}_{mes:02d}.xlsx"
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
