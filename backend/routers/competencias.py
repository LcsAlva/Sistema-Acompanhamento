"""Router de Competência Financeira — engine de governança mensal.

Prefixo: /api/competencias

Endpoints:
  GET  /api/competencias                      → lista competências
  GET  /api/competencias/{ano}/{mes}           → consulta competência
  POST /api/competencias/{ano}/{mes}/abrir     → cria como 'aberta'
  POST /api/competencias/{ano}/{mes}/em-apuracao → move para 'em_apuracao'
  POST /api/competencias/{ano}/{mes}/fechar    → move para 'fechada'
  POST /api/competencias/{ano}/{mes}/consolidar → move para 'consolidada'
  POST /api/competencias/{ano}/{mes}/encerrar  → encerra contabilmente + lock

Invariantes:
  • Transições inválidas retornam 422.
  • Competência encerrada/locked não aceita nenhuma transição.
  • Todos os movimentos ficam registrados em competencia_log.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import CompetenciaFinanceira, CompetenciaLog
from ..services import competencia_service as svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/competencias", tags=["competencias"])


# ── Schemas de entrada ───────────────────────────────────────────────────────

class AcaoCompetenciaIn(BaseModel):
    usuario: Optional[str] = None
    observacao: Optional[str] = None


# ── Helpers de serialização ──────────────────────────────────────────────────

def _serializar(comp: CompetenciaFinanceira) -> dict:
    return {
        "id":    comp.id,
        "ano":   comp.ano,
        "mes":   comp.mes,
        "competencia": f"{comp.ano}/{comp.mes:02d}",
        "status": comp.status,
        "status_label": svc.STATUS_LABEL.get(comp.status, comp.status),
        "locked": comp.locked,
        "proximos_status": svc.TRANSICOES.get(comp.status, []),
        # Rastreabilidade de cada transição
        "aberto_em":       comp.aberto_em.isoformat()      if comp.aberto_em      else None,
        "aberto_por":      comp.aberto_por,
        "em_apuracao_em":  comp.em_apuracao_em.isoformat() if comp.em_apuracao_em else None,
        "em_apuracao_por": comp.em_apuracao_por,
        "fechado_em":      comp.fechado_em.isoformat()     if comp.fechado_em     else None,
        "fechado_por":     comp.fechado_por,
        "consolidado_em":  comp.consolidado_em.isoformat() if comp.consolidado_em else None,
        "consolidado_por": comp.consolidado_por,
        "encerrado_em":    comp.encerrado_em.isoformat()   if comp.encerrado_em   else None,
        "encerrado_por":   comp.encerrado_por,
        "observacao":      comp.observacao,
        "created_at":      comp.created_at.isoformat()     if comp.created_at     else None,
        "updated_at":      comp.updated_at.isoformat()     if comp.updated_at     else None,
    }


def _serializar_log(log: CompetenciaLog) -> dict:
    return {
        "id":             log.id,
        "competencia_id": log.competencia_id,
        "evento":         log.evento,
        "status_antes":   log.status_antes,
        "status_depois":  log.status_depois,
        "usuario":        log.usuario,
        "observacao":     log.observacao,
        "criado_em":      log.criado_em.isoformat() if log.criado_em else None,
    }


def _get_ou_404(db: Session, ano: int, mes: int) -> CompetenciaFinanceira:
    comp = svc.get_competencia(db, ano, mes)
    if not comp:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Competência {ano}/{mes:02d} não encontrada. "
                f"Crie-a via POST /api/competencias/{ano}/{mes}/abrir."
            ),
        )
    return comp


def _handle_valor_error(exc: ValueError, ano: int, mes: int) -> None:
    raise HTTPException(status_code=422, detail=str(exc))


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get(
    "",
    summary="Listar competências financeiras",
    description="Retorna todas as competências financeiras, com filtros opcionais por status e ano.",
)
def listar_competencias(
    status: Optional[str] = Query(None, description="Filtrar por status"),
    ano:    Optional[int] = Query(None, description="Filtrar por ano"),
    db: Session = Depends(get_db),
):
    comps = svc.listar_competencias(db, status=status, ano=ano)
    return [_serializar(c) for c in comps]


@router.get(
    "/{ano}/{mes}",
    summary="Consultar competência",
    description="Retorna os detalhes e histórico de uma competência específica.",
)
def consultar_competencia(
    ano: int, mes: int,
    db: Session = Depends(get_db),
):
    comp = _get_ou_404(db, ano, mes)
    dados = _serializar(comp)
    dados["logs"] = [_serializar_log(lg) for lg in
                     sorted(comp.logs, key=lambda x: x.criado_em or 0)]
    return dados


@router.post(
    "/{ano}/{mes}/abrir",
    summary="Abrir competência",
    description="Cria a competência financeira do mês com status 'aberta'.",
    status_code=201,
)
def abrir_competencia(
    ano: int, mes: int,
    payload: AcaoCompetenciaIn = AcaoCompetenciaIn(),
    db: Session = Depends(get_db),
):
    _validar_mes(mes)
    try:
        comp = svc.abrir_competencia(db, ano, mes,
                                     usuario=payload.usuario,
                                     observacao=payload.observacao)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _serializar(comp)


@router.post(
    "/{ano}/{mes}/em-apuracao",
    summary="Mover para Em Apuração",
    description="Transiciona competência de 'aberta' para 'em_apuracao'. "
                "Ainda permite movimentos operacionais.",
)
def mover_para_em_apuracao(
    ano: int, mes: int,
    payload: AcaoCompetenciaIn = AcaoCompetenciaIn(),
    db: Session = Depends(get_db),
):
    _validar_mes(mes)
    try:
        comp = svc.mover_para_em_apuracao(db, ano, mes,
                                          usuario=payload.usuario,
                                          observacao=payload.observacao)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _serializar(comp)


@router.post(
    "/{ano}/{mes}/fechar",
    summary="Fechar competência",
    description="Transiciona para 'fechada'. Bloqueia alterações financeiras. "
                "Não reverte.",
)
def fechar_competencia(
    ano: int, mes: int,
    payload: AcaoCompetenciaIn = AcaoCompetenciaIn(),
    db: Session = Depends(get_db),
):
    _validar_mes(mes)
    try:
        comp = svc.fechar_competencia(db, ano, mes,
                                      usuario=payload.usuario,
                                      observacao=payload.observacao)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _serializar(comp)


@router.post(
    "/{ano}/{mes}/consolidar",
    summary="Consolidar competência",
    description="Transiciona para 'consolidada'. Indica que o BM foi consolidado "
                "e os dados são definitivos.",
)
def consolidar_competencia(
    ano: int, mes: int,
    payload: AcaoCompetenciaIn = AcaoCompetenciaIn(),
    db: Session = Depends(get_db),
):
    _validar_mes(mes)
    try:
        comp = svc.consolidar_competencia(db, ano, mes,
                                          usuario=payload.usuario,
                                          observacao=payload.observacao)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _serializar(comp)


@router.post(
    "/{ano}/{mes}/encerrar",
    summary="Encerrar contabilmente",
    description="Encerra a competência contabilmente e aplica lock permanente. "
                "Nenhuma alteração financeira será possível após este ponto.",
)
def encerrar_competencia(
    ano: int, mes: int,
    payload: AcaoCompetenciaIn = AcaoCompetenciaIn(),
    db: Session = Depends(get_db),
):
    _validar_mes(mes)
    try:
        comp = svc.encerrar_competencia(db, ano, mes,
                                        usuario=payload.usuario,
                                        observacao=payload.observacao)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _serializar(comp)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _validar_mes(mes: int) -> None:
    if not (1 <= mes <= 12):
        raise HTTPException(status_code=422, detail="Mês inválido. Use 1–12.")
