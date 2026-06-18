from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..services import performance_service as svc


router = APIRouter(prefix="/performance", tags=["performance"])


@router.get("/auditoria")
def obter_auditoria_integrada(recalcular: bool = False, db: Session = Depends(get_db)):
    return svc.obter_auditoria_integrada(db, recalcular=recalcular)
