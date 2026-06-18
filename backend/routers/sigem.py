"""Router SIGEM: importacao, consulta e conciliacao LD x SIGEM."""
from __future__ import annotations

import io
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from ..database import get_db
from ..parsers.sigem_parser import parse_sigem
from ..schemas import SigemDocumentoOut, SigemImportResultado
from ..services import sigem_service as svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sigem", tags=["sigem"])


@router.post("/upload", response_model=SigemImportResultado)
async def upload_sigem(
    arquivo: UploadFile = File(...),
    aba: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    conteudo = await arquivo.read()
    try:
        parsed = parse_sigem(io.BytesIO(conteudo), aba=aba)
    except Exception as e:
        logger.exception("Falha ao ler SIGEM")
        raise HTTPException(400, f"Erro ao ler o arquivo SIGEM: {e}")

    if not parsed["colunas_detectadas"].get("codigo_documento"):
        raise HTTPException(
            400,
            "Nao foi possivel detectar a coluna de documento do SIGEM. "
            f"Colunas reconhecidas: {list(parsed['colunas_detectadas'].keys()) or 'nenhuma'}.",
        )

    resultado = svc.importar_sigem(db, parsed["documentos"], origem_arquivo=arquivo.filename)
    resultado["colunas_detectadas"] = parsed["colunas_detectadas"]
    resultado["aba"] = parsed["aba"]
    resultado["linha_cabecalho"] = parsed["linha_cabecalho"]
    resultado["linhas_ignoradas"] = parsed["ignoradas"]
    return resultado


@router.get("/documentos", response_model=list[SigemDocumentoOut])
def listar_documentos(
    status: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    return svc.listar_documentos(db, status=status, q=q)


@router.get("/documentos/{codigo_documento}/status")
def obter_status_atual(codigo_documento: str, db: Session = Depends(get_db)):
    status = svc.obter_status_atual(db, codigo_documento)
    if status is None:
        raise HTTPException(404, "Documento nao encontrado no SIGEM")
    return {"codigo_documento": codigo_documento, "status": status, "origem_status": "SIGEM"}


@router.get("/sem-workflow", response_model=list[SigemDocumentoOut])
def documentos_sem_workflow(db: Session = Depends(get_db)):
    return svc.documentos_sem_workflow(db)


@router.get("/documentos-divergentes")
def documentos_divergentes(db: Session = Depends(get_db)):
    return svc.documentos_divergentes(db)


@router.get("/conciliacao")
def conciliacao(db: Session = Depends(get_db)):
    return svc.dashboard_conciliacao(db)


@router.get("/filtros")
def filtros(db: Session = Depends(get_db)):
    return {"status": svc.status_distintos(db)}
