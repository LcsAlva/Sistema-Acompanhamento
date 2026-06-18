"""Rotas do módulo Produção — importação do XER e painel executivo."""
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..parsers.xer_parser import extrair_producao
from ..services import producao_service as svc

router = APIRouter(prefix="/producao", tags=["producao"])


@router.post("/import-xer")
async def import_xer(arquivo: UploadFile = File(...), db: Session = Depends(get_db)):
    if not arquivo.filename.lower().endswith(".xer"):
        raise HTTPException(400, "Envie um arquivo .xer do Primavera P6.")
    raw = await arquivo.read()
    conteudo = raw.decode("cp1252", errors="replace")
    parsed = extrair_producao(conteudo)
    if not parsed["atividades"]:
        raise HTTPException(400, "Nenhuma atividade (TASK) encontrada no XER.")
    return svc.importar_xer(db, parsed, arquivo.filename)


@router.get("/status")
def status(db: Session = Depends(get_db)):
    p = svc.get_projeto_ativo(db)
    if not p:
        return {"tem_dados": False}
    return {"tem_dados": True, "proj_short_name": p.proj_short_name,
            "data_date": p.data_date.isoformat() if p.data_date else None,
            "total_atividades": p.total_atividades,
            "origem_arquivo": p.origem_arquivo}


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    return svc.dashboard(db)
