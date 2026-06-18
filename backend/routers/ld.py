"""Router de Integração LD / SIGEM (Módulo 1 — Fase 2A)."""
from __future__ import annotations

import io
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from ..database import get_db
from ..parsers.ld_parser import parse_ld
from ..schemas import LdDocumentoOut, LdHistoricoOut, LdImportResultado
from ..services import ld_service as svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ld", tags=["integracao-ld"])


@router.post("/upload", response_model=LdImportResultado)
async def upload_ld(
    arquivo: UploadFile = File(...),
    aba: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Importa a LD da S5: lê o Excel, faz upsert e registra histórico de status."""
    conteudo = await arquivo.read()
    try:
        parsed = parse_ld(io.BytesIO(conteudo), aba=aba)
    except Exception as e:
        logger.exception("Falha ao ler LD")
        raise HTTPException(400, f"Erro ao ler o arquivo LD: {e}")

    if not parsed["colunas_detectadas"].get("codigo_documento"):
        raise HTTPException(
            400,
            "Não foi possível detectar a coluna de código do documento. "
            f"Colunas reconhecidas: {list(parsed['colunas_detectadas'].keys()) or 'nenhuma'}.",
        )

    resultado = svc.importar_ld(db, parsed["documentos"], origem_arquivo=arquivo.filename)
    resultado["colunas_detectadas"] = parsed["colunas_detectadas"]
    resultado["aba"] = parsed["aba"]
    resultado["linha_cabecalho"] = parsed["linha_cabecalho"]
    resultado["linhas_ignoradas"] = parsed["ignoradas"]
    return resultado


@router.get("/documentos", response_model=list[LdDocumentoOut])
def listar_documentos(
    disciplina: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    return svc.listar_documentos(db, disciplina=disciplina, status=status, q=q)


@router.get("/documentos/{documento_id}/historico", response_model=list[LdHistoricoOut])
def historico(documento_id: int, db: Session = Depends(get_db)):
    return svc.historico(db, documento_id)


@router.get("/filtros")
def filtros(db: Session = Depends(get_db)):
    """Valores distintos para popular filtros da tela."""
    return {
        "disciplinas": svc.disciplinas_distintas(db),
        "status": svc.status_distintos(db),
    }
