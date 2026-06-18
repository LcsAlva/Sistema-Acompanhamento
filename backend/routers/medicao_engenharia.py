"""Router do Motor de Medição de Engenharia (Módulo 2 — Fase 2A)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..services import motor_medicao_service as svc

router = APIRouter(prefix="/medicao-eng", tags=["medicao-engenharia"])


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    """Totais globais: Documentos Totais, Em Elaboração, Em Análise,
    Sem Workflow, % Medido."""
    return svc.dashboard(db)


@router.get("/por-disciplina")
def por_disciplina(db: Session = Depends(get_db)):
    """Medição por disciplina (docs, medidos, A4 acumulado, % medição)."""
    return svc.medicao_por_disciplina(db)


@router.get("/evolucao")
def evolucao(semanas: int = Query(12, ge=1, le=104), db: Session = Depends(get_db)):
    """Série semanal de documentos aptos (SEM WORKFLOW), reconstruída do histórico."""
    return svc.evolucao_semanal(db, semanas=semanas)


@router.get("/config")
def config():
    """Configuração efetiva do motor (status aptos, pesos) — parametrização."""
    cfg = svc.load_config()
    return {
        "status_aptos": sorted(cfg["status_aptos"]),
        "status_em_elaboracao": sorted(cfg["status_em_elaboracao"]),
        "status_em_analise": sorted(cfg["status_em_analise"]),
        "peso_por": cfg["peso_por"],
    }
