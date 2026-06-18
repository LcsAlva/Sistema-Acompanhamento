from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..services import economico_service as svc


router = APIRouter(prefix="/economico", tags=["economico"])


class ForecastOperacionalCreate(BaseModel):
    nome: str | None = None
    motivo: str | None = None
    usuario: str | None = "sistema"
    importacao_id: int | None = None


class ForecastOperacionalClone(BaseModel):
    nome: str | None = None
    motivo: str | None = None
    usuario: str | None = "sistema"


class ForecastOperacionalAjuste(BaseModel):
    categoria: str
    valor_novo: float
    justificativa: str
    usuario: str | None = "sistema"


@router.post("/importar")
async def importar_planilha_economica(
    file: UploadFile = File(...),
    usuario: str | None = Form("sistema"),
    db: Session = Depends(get_db),
):
    if not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(400, "Envie uma planilha .xlsx ou .xlsm.")
    conteudo = await file.read()
    try:
        return svc.importar_e_auditar(db, conteudo, file.filename, usuario)
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(500, f"Erro ao importar planilha econômica: {e}")


@router.get("/importacoes")
def listar_importacoes(db: Session = Depends(get_db)):
    return [
        {
            "id": imp.id,
            "arquivo_original": imp.arquivo_original,
            "importado_em": imp.importado_em,
            "usuario": imp.usuario,
            "status": imp.status,
            "observacao": imp.observacao,
        }
        for imp in svc.listar_importacoes(db)
    ]


@router.get("/auditoria")
def obter_auditoria(importacao_id: int | None = None, db: Session = Depends(get_db)):
    return svc.obter_auditoria(db, importacao_id)


@router.get("/auditoria-receitas")
def obter_auditoria_receitas(importacao_id: int | None = None, db: Session = Depends(get_db)):
    return svc.obter_auditoria_receitas(db, importacao_id)


@router.get("/dashboard")
def obter_dashboard(importacao_id: int | None = None, db: Session = Depends(get_db)):
    return svc.obter_dashboard(db, importacao_id)


@router.get("/receitas")
def obter_receitas(importacao_id: int | None = None, db: Session = Depends(get_db)):
    return svc.obter_receitas(db, importacao_id)


@router.get("/forecast")
def obter_forecast(importacao_id: int | None = None, db: Session = Depends(get_db)):
    return svc.obter_forecast(db, importacao_id)


@router.get("/forecast-operacional/versoes")
def listar_forecast_operacional_versoes(db: Session = Depends(get_db)):
    return svc.listar_forecast_operacional_versoes(db)


@router.post("/forecast-operacional/versoes")
def criar_forecast_operacional_versao(payload: ForecastOperacionalCreate, db: Session = Depends(get_db)):
    try:
        return svc.criar_forecast_operacional_versao(
            db,
            nome=payload.nome,
            motivo=payload.motivo,
            usuario=payload.usuario,
            importacao_id=payload.importacao_id,
        )
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.get("/forecast-operacional/comparar")
def comparar_forecast_operacional_versoes(base_id: int, novo_id: int, db: Session = Depends(get_db)):
    try:
        return svc.comparar_forecast_operacional_versoes(db, base_id, novo_id)
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.get("/forecast-operacional/versoes/{versao_id}")
def obter_forecast_operacional_versao(versao_id: int, db: Session = Depends(get_db)):
    try:
        return svc.obter_forecast_operacional_versao(db, versao_id)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/forecast-operacional/versoes/{versao_id}/clonar")
def clonar_forecast_operacional_versao(
    versao_id: int,
    payload: ForecastOperacionalClone,
    db: Session = Depends(get_db),
):
    try:
        return svc.clonar_forecast_operacional_versao(
            db,
            versao_id,
            nome=payload.nome,
            motivo=payload.motivo,
            usuario=payload.usuario,
        )
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.post("/forecast-operacional/versoes/{versao_id}/ajustes")
def ajustar_forecast_operacional_categoria(
    versao_id: int,
    payload: ForecastOperacionalAjuste,
    db: Session = Depends(get_db),
):
    try:
        return svc.ajustar_forecast_operacional_categoria(
            db,
            versao_id,
            categoria=payload.categoria,
            valor_novo=payload.valor_novo,
            justificativa=payload.justificativa,
            usuario=payload.usuario,
        )
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.get("/resultado")
def obter_resultado(importacao_id: int | None = None, db: Session = Depends(get_db)):
    return svc.obter_resultado(db, importacao_id)


@router.get("/historico")
def obter_historico(db: Session = Depends(get_db)):
    return svc.obter_historico(db)


@router.get("/custos")
def obter_custos(importacao_id: int | None = None, db: Session = Depends(get_db)):
    return svc.obter_custos(db, importacao_id)


@router.get("/desvios")
def obter_desvios(importacao_id: int | None = None, db: Session = Depends(get_db)):
    return svc.obter_desvios(db, importacao_id)


@router.get("/lancamentos")
def obter_lancamentos(
    importacao_id: int | None = None,
    categoria: str | None = None,
    fornecedor: str | None = None,
    conta: str | None = None,
    documento: str | None = None,
    periodo_inicio: date | None = None,
    periodo_fim: date | None = None,
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return svc.obter_lancamentos(
        db,
        importacao_id=importacao_id,
        categoria=categoria,
        fornecedor=fornecedor,
        conta=conta,
        documento=documento,
        periodo_inicio=periodo_inicio,
        periodo_fim=periodo_fim,
        limit=limit,
    )


@router.get("/centro-analise")
def obter_centro_analise(
    importacao_id: int | None = None,
    categoria: str | None = None,
    fornecedor: str | None = None,
    conta: str | None = None,
    documento: str | None = None,
    periodo_inicio: date | None = None,
    periodo_fim: date | None = None,
    db: Session = Depends(get_db),
):
    return svc.obter_centro_analise(
        db,
        importacao_id=importacao_id,
        categoria=categoria,
        fornecedor=fornecedor,
        conta=conta,
        documento=documento,
        periodo_inicio=periodo_inicio,
        periodo_fim=periodo_fim,
    )
