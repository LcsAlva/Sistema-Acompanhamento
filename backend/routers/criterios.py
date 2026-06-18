"""Router da Matriz de Critérios de Medição (Módulo 3 — Fase 2A)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import CriterioIn, CriterioOut, CriterioAvaliacaoOut
from ..services import criterios_service as svc

router = APIRouter(prefix="/criterios", tags=["criterios"])


@router.get("/tipos")
def listar_tipos():
    """Catálogo de tipos de critério disponíveis (com flag de implementado)."""
    return [{"tipo": t, **info} for t, info in svc.TIPOS_CRITERIO.items()]


@router.get("", response_model=list[CriterioOut])
def listar(
    tipo: Optional[str] = Query(None),
    ativo: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
):
    return svc.listar_criterios(db, tipo=tipo, ativo=ativo)


@router.post("", response_model=CriterioOut, status_code=201)
def upsert(payload: CriterioIn, db: Session = Depends(get_db)):
    if payload.tipo_criterio and payload.tipo_criterio not in svc.TIPOS_CRITERIO:
        raise HTTPException(400, f"tipo_criterio inválido: {payload.tipo_criterio}")
    return svc.upsert_criterio(db, payload.model_dump())


@router.put("/{codigo_eap}", response_model=CriterioOut)
def atualizar(codigo_eap: str, payload: CriterioIn, db: Session = Depends(get_db)):
    if payload.tipo_criterio and payload.tipo_criterio not in svc.TIPOS_CRITERIO:
        raise HTTPException(400, f"tipo_criterio inválido: {payload.tipo_criterio}")
    data = payload.model_dump()
    data["codigo_eap"] = codigo_eap
    return svc.upsert_criterio(db, data)


@router.delete("/{codigo_eap}", status_code=204)
def deletar(codigo_eap: str, db: Session = Depends(get_db)):
    if not svc.deletar_criterio(db, codigo_eap):
        raise HTTPException(404, "Critério não encontrado.")


@router.post("/seed")
def seed(tipo_default: str = Query(svc.TIPO_DEFAULT), db: Session = Depends(get_db)):
    """Cria critério default para cada item EAP sem critério (idempotente)."""
    if tipo_default not in svc.TIPOS_CRITERIO:
        raise HTTPException(400, f"tipo_default inválido: {tipo_default}")
    return svc.seed_from_eap(db, tipo_default=tipo_default)


@router.get("/{codigo_eap}/avaliar", response_model=CriterioAvaliacaoOut)
def avaliar(codigo_eap: str, db: Session = Depends(get_db)):
    """Resolve o handler do critério e devolve o % medido + evidências."""
    return svc.avaliar_criterio(db, codigo_eap)
