from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import RelatorioSemana
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/relatorio", tags=["relatorio"])

class RelatorioIn(BaseModel):
    semana: str
    descricao_resumida: Optional[str] = None
    justificativas_atraso: Optional[str] = None
    marcos_observacoes: Optional[str] = None
    condicoes_climaticas: Optional[str] = None
    nota_clima: Optional[str] = None

@router.get("/{semana}")
def get_relatorio(semana: str, db: Session = Depends(get_db)):
    r = db.query(RelatorioSemana).filter(RelatorioSemana.semana == semana).first()
    if not r:
        return {"semana": semana, "descricao_resumida": None, "justificativas_atraso": "[]",
                "marcos_observacoes": "[]", "condicoes_climaticas": None, "nota_clima": None}
    return r

@router.post("/{semana}")
def save_relatorio(semana: str, data: RelatorioIn, db: Session = Depends(get_db)):
    r = db.query(RelatorioSemana).filter(RelatorioSemana.semana == semana).first()
    if not r:
        r = RelatorioSemana(semana=semana)
        db.add(r)
    for field in ["descricao_resumida","justificativas_atraso","marcos_observacoes","condicoes_climaticas","nota_clima"]:
        val = getattr(data, field)
        if val is not None:
            setattr(r, field, val)
    db.commit()
    db.refresh(r)
    return r
