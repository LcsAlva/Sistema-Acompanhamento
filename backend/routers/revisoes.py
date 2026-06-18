"""Router de analise de revisoes LD/SIGEM."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import (
    AnaliseRevisaoUpdate,
    ControleDocumentoIn,
    ControleDocumentoOut,
    EventoRevisaoOut,
)
from ..services import revisoes_service as svc


router = APIRouter(prefix="/revisoes", tags=["revisoes-documentos"])


@router.get("/eventos", response_model=list[EventoRevisaoOut])
def listar_eventos(
    status: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    return svc.listar_eventos(db, status=status, q=q)


@router.patch("/eventos/{evento_id}", response_model=dict)
def atualizar_analise(
    evento_id: int,
    payload: AnaliseRevisaoUpdate,
    db: Session = Depends(get_db),
):
    try:
        evento = svc.atualizar_analise(db, evento_id, payload)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    return {
        "id": evento.id,
        "status_analise": evento.status_analise,
        "diferenca_quantidade": evento.diferenca_quantidade,
        "data_analise": evento.data_analise,
    }


@router.get("/controles", response_model=list[ControleDocumentoOut])
def listar_controles(
    documento: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    return svc.listar_controles(db, documento=documento, q=q)


@router.post("/controles", response_model=ControleDocumentoOut)
def criar_controle(
    payload: ControleDocumentoIn,
    db: Session = Depends(get_db),
):
    try:
        return svc.criar_controle(db, payload)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
