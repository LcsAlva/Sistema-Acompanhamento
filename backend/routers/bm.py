"""Router do módulo de Boletim de Medição (BM) — arquitetura refatorada.

Prefixo: /api/bm

Fluxo de aprovação (endpoint /status):
  em_previa → em_analise → pre_aprovada (e retornos)

Fluxo financeiro (endpoints exclusivos):
  POST /bm/{id}/fechar       → pre_aprovada → fechada (consolida + pendências)
  POST /bm/{id}/consolidar   → fechada → consolidada

Previsão:
  POST /bm/previsao/fechar   → congela previsão antes de abrir BM
  POST /bm/previsao/reabrir  → reabre previsão (só se BM em prévia)
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    BmCiclo, BmPendencia, BmVersao, BmSnapshotPrevisao,
    BmLancamento, BmConsolidado, BmLog, EapItem,
)
from ..services import bm_service as svc

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/bm", tags=["bm"])


# ── Schemas de entrada ───────────────────────────────────────────────────────

class AbrirBmIn(BaseModel):
    ano: int
    mes: int
    criado_por: Optional[str] = None
    observacao: Optional[str] = None


class LancamentoItemIn(BaseModel):
    eap_codigo: str
    pct_acumulado: float       # 0.0–1.0
    observacao: Optional[str] = None

    @field_validator('pct_acumulado')
    @classmethod
    def validar_range(cls, v: float) -> float:
        # Sem tolerância: 0.0 e 1.0 são os limites absolutos.
        # Valores negativos ou >100% são financeiramente impossíveis.
        if v < 0.0:
            raise ValueError(
                f'pct_acumulado inválido: {v} é negativo. '
                'Valores permitidos: 0% até 100%.'
            )
        if v > 1.0:
            raise ValueError(
                f'pct_acumulado inválido: {v} excede 100% (1.0). '
                'Valores permitidos: 0% até 100%.'
            )
        return v


class SalvarLancamentosIn(BaseModel):
    lancamentos: list[LancamentoItemIn]
    salvo_por: Optional[str] = None


class TransicionarStatusIn(BaseModel):
    novo_status: str
    usuario: Optional[str] = None
    observacao: Optional[str] = None


class FecharBmIn(BaseModel):
    fechado_por: Optional[str] = None
    observacao: Optional[str] = None


class ConsolidarBmIn(BaseModel):
    consolidado_por: Optional[str] = None
    observacao: Optional[str] = None


class RedistribuirIn(BaseModel):
    destino_ano: int
    destino_mes: int
    # Fração do SALDO RESTANTE a redistribuir (0.0–1.0).
    # 1.0 = redistribui tudo que ainda resta.
    pct_redistribuir: float
    redistribuido_por: Optional[str] = None
    observacao: Optional[str] = None

    @field_validator('pct_redistribuir')
    @classmethod
    def validar_pct(cls, v: float) -> float:
        # Sem tolerância: deve ser estritamente >0 e ≤1.0.
        if v <= 0.0:
            raise ValueError(
                f'pct_redistribuir inválido: {v} ≤ 0. '
                'Deve ser maior que 0% (redistribuir ao menos algo).'
            )
        if v > 1.0:
            raise ValueError(
                f'pct_redistribuir inválido: {v} excede 100% (1.0). '
                'Valores permitidos: 0% até 100%.'
            )
        return v


class FecharPrevisaoIn(BaseModel):
    ano: int
    mes: int
    fechado_por: Optional[str] = None


class ReabrirPrevisaoIn(BaseModel):
    ano: int
    mes: int
    reaberto_por: Optional[str] = None


# ── Previsão Mensal — gerenciamento de status ────────────────────────────────

@router.post("/previsao/fechar")
def fechar_previsao(payload: FecharPrevisaoIn, db: Session = Depends(get_db)):
    """Congela a previsão do mês para permitir abertura do BM.

    Deve ser executado ANTES de abrir o BM.
    Marca todos os itens de eap_previsao_mensal do mês como 'fechada'.
    """
    try:
        return svc.fechar_previsao_mensal(db, payload.ano, payload.mes, payload.fechado_por)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/previsao/reabrir")
def reabrir_previsao(payload: ReabrirPrevisaoIn, db: Session = Depends(get_db)):
    """Reabre a previsão fechada para edição.

    Só permitido se não há BM ou se o BM está em 'em_previa'.
    Previsões 'convertida' (snapshot já tirado) NÃO podem ser reabertas.
    """
    try:
        return svc.reabrir_previsao_mensal(db, payload.ano, payload.mes, payload.reaberto_por)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/previsao/status/{ano}/{mes}")
def status_previsao(ano: int, mes: int, db: Session = Depends(get_db)):
    """Retorna o status atual da previsão de um mês."""
    from ..models import EapPrevisaoMensal
    prevs = db.query(
        EapPrevisaoMensal.status_previsao,
        EapPrevisaoMensal.eap_codigo,
    ).filter(
        EapPrevisaoMensal.ano == ano,
        EapPrevisaoMensal.mes == mes,
    ).all()

    if not prevs:
        return {"ano": ano, "mes": mes, "status": "sem_previsao", "total": 0}

    from collections import Counter
    contagem = Counter(p.status_previsao for p in prevs)
    status_dominante = contagem.most_common(1)[0][0]

    return {
        "ano": ano, "mes": mes,
        "status": status_dominante,
        "total": len(prevs),
        "por_status": dict(contagem),
        "pode_abrir_bm": all(s in ('fechada', 'convertida') for s in contagem),
    }


# ── Migração legado ───────────────────────────────────────────────────────────

@router.post("/migrar-legado", tags=["bm", "admin"])
def migrar_ciclos_legados(db: Session = Depends(get_db)):
    """Migra CicloMedicao legados para o novo sistema BmCiclo. Idempotente."""
    from ..models import CicloMedicao, LancamentoMedicao
    import json

    ciclos_leg = (
        db.query(CicloMedicao).order_by(CicloMedicao.ano, CicloMedicao.mes).all()
    )
    todos = db.query(EapItem).all()
    pais  = {it.parent_codigo for it in todos if it.parent_codigo}
    folhas = {it.codigo for it in todos if it.codigo not in pais}

    migrados = 0
    ja_existiam = 0

    for cl in ciclos_leg:
        existe = db.query(BmCiclo).filter(
            BmCiclo.ano == cl.ano, BmCiclo.mes == cl.mes
        ).first()
        if existe:
            ja_existiam += 1
            continue

        status_novo = "fechada" if cl.status == "fechado" else "em_previa"
        ciclo = BmCiclo(
            ano=cl.ano, mes=cl.mes,
            status=status_novo,
            numero_bm=f"BM-{cl.ano:04d}-{cl.mes:02d}",
            ciclo_legado_id=cl.id,
            criado_por="migração",
            criado_em=cl.criado_em,
            fechado_em=cl.fechado_em,
            fechado_por=cl.fechado_por,
            observacao=cl.observacao,
        )
        db.add(ciclo)
        db.flush()

        lancs = db.query(LancamentoMedicao).filter(
            LancamentoMedicao.ciclo_id == cl.id
        ).all()
        for l in lancs:
            db.add(BmLancamento(
                ciclo_id=ciclo.id,
                eap_codigo=l.eap_codigo,
                pct_acumulado=float(l.pct_acumulado or 0.0),
                observacao=l.observacao,
                atualizado_por="migração",
            ))

        svc._criar_snapshot_previsao(db, ciclo)

        if cl.status == "fechado":
            try:
                svc._materializar_consolidado(db, ciclo)
                svc._gerar_pendencias(db, ciclo)
            except Exception as e:
                logger.warning("Falha ao materializar %d/%d: %s", cl.ano, cl.mes, e)

        migrados += 1

    db.commit()
    return {
        "migrados": migrados,
        "ja_existiam": ja_existiam,
        "total_ciclos_legado": len(ciclos_leg),
    }


# ── CRUD do BM ───────────────────────────────────────────────────────────────

@router.post("/abrir", status_code=201)
def abrir_bm(payload: AbrirBmIn, db: Session = Depends(get_db)):
    """Abre o BM do mês. Exige previsão fechada."""
    try:
        ciclo = svc.abrir_bm(db, payload.ano, payload.mes,
                             payload.criado_por, payload.observacao)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return svc.montar_bm_completo(db, ciclo.id)


@router.get("/lista")
def listar_bms(status: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(BmCiclo)
    if status:
        q = q.filter(BmCiclo.status == status)
    ciclos = q.order_by(BmCiclo.ano.desc(), BmCiclo.mes.desc()).all()
    _MES = {1:'jan',2:'fev',3:'mar',4:'abr',5:'mai',6:'jun',
            7:'jul',8:'ago',9:'set',10:'out',11:'nov',12:'dez'}
    return [
        {
            "id": c.id, "ano": c.ano, "mes": c.mes,
            "label": f"{_MES[c.mes]}/{str(c.ano)[2:]}",
            "numero_bm": c.numero_bm, "status": c.status,
            "criado_em": c.criado_em.isoformat() if c.criado_em else None,
            "fechado_em": c.fechado_em.isoformat() if c.fechado_em else None,
            "fechado_por": c.fechado_por,
        }
        for c in ciclos
    ]


@router.get("/mes/{ano}/{mes}")
def get_bm_por_mes(ano: int, mes: int, db: Session = Depends(get_db)):
    """Retorna o BM de um mês. Retorna 404 se não existir.

    GET nunca cria dados — use POST /bm/abrir para criar o BM.
    Esta separação é intencional: GET é idempotente e seguro.
    """
    ciclo = db.query(BmCiclo).filter(BmCiclo.ano == ano, BmCiclo.mes == mes).first()
    if not ciclo:
        raise HTTPException(
            404,
            f"BM {ano}/{mes:02d} não encontrado. "
            "Use POST /api/bm/abrir para criar o BM deste mês."
        )
    return svc.montar_bm_completo(db, ciclo.id)


@router.get("/{ciclo_id}")
def get_bm(ciclo_id: int, db: Session = Depends(get_db)):
    try:
        return svc.montar_bm_completo(db, ciclo_id)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.put("/{ciclo_id}/lancamentos")
def salvar_lancamentos(
    ciclo_id: int,
    body: SalvarLancamentosIn,
    db: Session = Depends(get_db),
):
    """Salva lançamentos com validações de integridade.

    Validações:
    - Somente itens folha da EAP
    - pct_acumulado ∈ [0, 1]
    - Sem regressão abaixo do acumulado já consolidado
    """
    try:
        ciclo = svc.salvar_lancamentos(
            db, ciclo_id,
            [i.model_dump() for i in body.lancamentos],
            body.salvo_por,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return svc.montar_bm_completo(db, ciclo.id)


@router.post("/{ciclo_id}/status")
def transicionar_status(
    ciclo_id: int,
    body: TransicionarStatusIn,
    db: Session = Depends(get_db),
):
    """Transiciona o status do BM no fluxo de aprovação.

    Transições permitidas neste endpoint:
      em_previa → em_analise
      em_analise → pre_aprovada  (ou voltar para em_previa)
      pre_aprovada → em_analise  (retorno para revisão)

    Para fechamento use POST /{id}/fechar.
    Para consolidação use POST /{id}/consolidar.
    """
    try:
        ciclo = svc.transicionar_status(
            db, ciclo_id, body.novo_status, body.usuario, body.observacao,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"status": ciclo.status, "mensagem": f"Status atualizado para '{ciclo.status}'"}


@router.post("/{ciclo_id}/fechar")
def fechar_bm(
    ciclo_id: int,
    body: FecharBmIn,
    db: Session = Depends(get_db),
):
    """Fecha o BM — operação financeiramente crítica e atômica.

    Exige status == pre_aprovada.
    Consolida acumulados, propaga hierarquia EAP e gera pendências.
    Após fechamento: BM imutável. Qualquer ajuste via complemento/aditivo.
    """
    try:
        ciclo = svc.fechar_bm(db, ciclo_id, body.fechado_por, body.observacao)
    except ValueError as e:
        raise HTTPException(400, str(e))
    dados = svc.montar_bm_completo(db, ciclo.id)
    return {
        **dados,
        "mensagem": "BM fechado com sucesso. Consolidação realizada.",
        "pendencias_geradas": len(dados.get("pendencias", [])),
    }


@router.post("/{ciclo_id}/consolidar")
def consolidar_bm(
    ciclo_id: int,
    body: ConsolidarBmIn,
    db: Session = Depends(get_db),
):
    """Consolida o BM — transição final após conferência pós-fechamento.

    Exige status == fechada.
    Status terminal: não pode ser revertido.
    """
    try:
        ciclo = svc.consolidar_bm(
            db, ciclo_id, body.consolidado_por, body.observacao
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {
        "status": ciclo.status,
        "consolidado_em": ciclo.consolidado_em.isoformat() if ciclo.consolidado_em else None,
        "mensagem": f"BM {ciclo.numero_bm} consolidado com sucesso.",
    }


# ── Pendências ───────────────────────────────────────────────────────────────

@router.get("/{ciclo_id}/pendencias")
def get_pendencias_bm(ciclo_id: int, db: Session = Depends(get_db)):
    ciclo = db.query(BmCiclo).filter(BmCiclo.id == ciclo_id).first()
    if not ciclo:
        raise HTTPException(404, "BM não encontrado.")
    return svc.get_pendencias_ativas(db, ano=ciclo.ano, mes=ciclo.mes)


@router.get("/pendencias/todas")
def get_todas_pendencias(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    return svc.get_pendencias_ativas(db)


@router.post("/pendencias/{pendencia_id}/redistribuir")
def redistribuir_pendencia(
    pendencia_id: int,
    body: RedistribuirIn,
    db: Session = Depends(get_db),
):
    """Redistribui pendência para mês futuro.

    pct_redistribuir é fração do SALDO RESTANTE (não do gap total):
      - 1.0 → redistribui 100% do que ainda resta
      - 0.5 → redistribui 50% do que ainda resta

    Bloqueia redistribuição para meses com BM fechado/consolidado.
    """
    try:
        pend = svc.redistribuir_pendencia(
            db, pendencia_id,
            body.destino_ano, body.destino_mes,
            body.pct_redistribuir,
            body.redistribuido_por, body.observacao,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    saldo = round((pend.pct_gap - pend.pct_ja_redistribuido) * 100, 4)
    return {
        "mensagem": "Pendência redistribuída com sucesso.",
        "status_pendencia": pend.status,
        "pct_saldo_restante": saldo,
        "previsao_destino_atualizada": f"{body.destino_ano}/{body.destino_mes:02d}",
    }


# ── Dashboard (somente BMs fechados) ─────────────────────────────────────────

@router.get("/dashboard/curva-s")
def dashboard_curva_s(db: Session = Depends(get_db)):
    """Curva-S financeira. SOMENTE dados de BMs fechados/consolidados."""
    return svc.get_curva_s_consolidada(db)


@router.get("/dashboard/kpis")
def dashboard_kpis(db: Session = Depends(get_db)):
    """KPIs financeiros (BAC, PV, EV, SPI, CV%, VAC). Calculados sobre BMs fechados."""
    return svc.get_kpis_dashboard(db)


@router.get("/dashboard/historico")
def dashboard_historico(db: Session = Depends(get_db)):
    """Histórico resumido de todos os BMs fechados."""
    ciclos = (
        db.query(BmCiclo)
        .filter(BmCiclo.status.in_(["fechada", "consolidada"]))
        .order_by(BmCiclo.ano.desc(), BmCiclo.mes.desc())
        .all()
    )
    _MES = {1:'jan',2:'fev',3:'mar',4:'abr',5:'mai',6:'jun',
            7:'jul',8:'ago',9:'set',10:'out',11:'nov',12:'dez'}
    bac = svc._bac(db)
    result = []
    for c in ciclos:
        cons_n1 = (
            db.query(BmConsolidado)
            .filter(BmConsolidado.ciclo_id == c.id, BmConsolidado.nivel == 1)
            .all()
        )
        ev_acum = sum(x.valor_acumulado for x in cons_n1) if cons_n1 else 0.0
        ev_per  = sum(x.valor_periodo   for x in cons_n1) if cons_n1 else 0.0
        result.append({
            "ciclo_id": c.id,
            "numero_bm": c.numero_bm,
            "ano": c.ano, "mes": c.mes,
            "label": f"{_MES[c.mes]}/{str(c.ano)[2:]}",
            "status": c.status,
            "fechado_em": c.fechado_em.isoformat() if c.fechado_em else None,
            "fechado_por": c.fechado_por,
            "ev_periodo": round(ev_per, 2),
            "ev_acumulado": round(ev_acum, 2),
            "pct_acum": round(ev_acum / bac, 6) if bac else 0.0,
        })
    return result


# ── Audit trail ──────────────────────────────────────────────────────────────

@router.get("/{ciclo_id}/versoes")
def get_versoes(ciclo_id: int, db: Session = Depends(get_db)):
    ciclo = db.query(BmCiclo).filter(BmCiclo.id == ciclo_id).first()
    if not ciclo:
        raise HTTPException(404, "BM não encontrado.")
    versoes = (
        db.query(BmVersao)
        .filter(BmVersao.ciclo_id == ciclo_id)
        .order_by(BmVersao.numero_versao.desc())
        .all()
    )
    return [
        {
            "numero": v.numero_versao,
            "status_no_momento": v.status_no_momento,
            "total_valor_periodo": v.total_valor_periodo,
            "pct_acum_projeto": round(v.pct_acum_projeto * 100, 4),
            "criado_em": v.criado_em.isoformat() if v.criado_em else None,
            "criado_por": v.criado_por,
        }
        for v in versoes
    ]


@router.get("/{ciclo_id}/log")
def get_log_bm(ciclo_id: int, db: Session = Depends(get_db)):
    """Trilha de auditoria completa do BM."""
    ciclo = db.query(BmCiclo).filter(BmCiclo.id == ciclo_id).first()
    if not ciclo:
        raise HTTPException(404, "BM não encontrado.")
    logs = (
        db.query(BmLog)
        .filter(BmLog.ciclo_id == ciclo_id)
        .order_by(BmLog.criado_em.desc())
        .all()
    )
    return [
        {
            "id": l.id,
            "evento": l.evento,
            "usuario": l.usuario,
            "detalhe": l.detalhe,
            "valor_antes": l.valor_antes,
            "valor_depois": l.valor_depois,
            "criado_em": l.criado_em.isoformat() if l.criado_em else None,
        }
        for l in logs
    ]


@router.get("/{ciclo_id}/snapshot-previsao")
def get_snapshot_previsao(ciclo_id: int, db: Session = Depends(get_db)):
    ciclo = db.query(BmCiclo).filter(BmCiclo.id == ciclo_id).first()
    if not ciclo:
        raise HTTPException(404, "BM não encontrado.")
    snaps = (
        db.query(BmSnapshotPrevisao, EapItem)
        .join(EapItem, EapItem.codigo == BmSnapshotPrevisao.eap_codigo)
        .filter(BmSnapshotPrevisao.ciclo_id == ciclo_id)
        .order_by(BmSnapshotPrevisao.eap_codigo)
        .all()
    )
    return [
        {
            "eap_codigo": s.eap_codigo,
            "descricao": it.descricao,
            "nivel": it.nivel,
            "valor_item": it.valor or 0.0,
            "pct_previsto": round(s.pct_previsto * 100, 4),
            "adiantada": s.adiantada,
            "mes_origem": f"{s.mes_origem_ano}/{s.mes_origem_mes:02d}"
                          if s.mes_origem_ano else None,
            "capturado_em": s.capturado_em.isoformat() if s.capturado_em else None,
        }
        for s, it in snaps
    ]


# ── PDF ───────────────────────────────────────────────────────────────────────

@router.get("/{ciclo_id}/pdf")
def gerar_pdf_bm(ciclo_id: int, db: Session = Depends(get_db)):
    ciclo = db.query(BmCiclo).filter(BmCiclo.id == ciclo_id).first()
    if not ciclo:
        raise HTTPException(404, "BM não encontrado.")

    dados = svc.montar_bm_completo(db, ciclo_id)

    from ..models import CicloMedicao as _CM
    from ..utils.gerar_previa_pdf import gerar_previa_pdf

    ciclo_leg = (
        db.query(_CM).filter(_CM.id == ciclo.ciclo_legado_id).first()
        if ciclo.ciclo_legado_id else None
    )
    if not ciclo_leg:
        raise HTTPException(422, "PDF requer sincronização com ciclo legado.")

    class _FakeCiclo:
        pass
    fc = _FakeCiclo()
    for k, v in {
        "id": ciclo_leg.id, "ano": ciclo.ano, "mes": ciclo.mes,
        "status": "fechado" if ciclo.status in ("fechada", "consolidada") else "aberto",
        "fechado_em": ciclo.fechado_em, "fechado_por": ciclo.fechado_por,
        "observacao": ciclo.observacao, "criado_em": ciclo.criado_em,
    }.items():
        setattr(fc, k, v)

    try:
        pdf_bytes = gerar_previa_pdf({"ciclo": fc, **dados})
    except Exception as e:
        logger.exception("Erro ao gerar PDF do BM")
        raise HTTPException(500, f"Erro ao gerar PDF: {e}")

    status_lbl = "FECHADO" if ciclo.status in ("fechada", "consolidada") else "PREVIA"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition":
                 f'attachment; filename="BM-{ciclo.ano}-{ciclo.mes:02d}-{status_lbl}.pdf"'},
    )


@router.get("/{ciclo_id}/anexo-resumo-pdf")
def gerar_pdf_anexo_resumo_bm(ciclo_id: int, db: Session = Depends(get_db)):
    ciclo = db.query(BmCiclo).filter(BmCiclo.id == ciclo_id).first()
    if not ciclo:
        raise HTTPException(404, "BM nÃ£o encontrado.")

    dados = svc.montar_bm_completo(db, ciclo_id)

    try:
        from ..utils.gerar_fiscalizacao_pdf import gerar_fiscalizacao_pdf

        pdf_bytes = gerar_fiscalizacao_pdf(dados)
    except Exception as e:
        logger.exception("Erro ao gerar PDF do ANEXO I - RESUMO BM")
        raise HTTPException(500, f"Erro ao gerar PDF do ANEXO I: {e}")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition":
                 f'attachment; filename="ANEXO-I-RESUMO-BM-{ciclo.ano}-{ciclo.mes:02d}.pdf"'},
    )
