"""
Relatório Fotográfico — Fotos de evidência por item EAP por ciclo de medição.
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, Body
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import FotoMedicao
from ..schemas import FotoOut, FotoLegendaIn

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/medicao", tags=["fotos"])

# Diretório base para uploads (backend/uploads)
_BASE_UPLOADS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
_FOTOS_DIR = os.path.join(_BASE_UPLOADS, "fotos")


def _renumerar(db: Session, ano: int, mes: int) -> None:
    """Renumera todas as fotos de um ciclo ordenado por (eap_codigo, id)."""
    fotos = (
        db.query(FotoMedicao)
        .filter(FotoMedicao.ano == ano, FotoMedicao.mes == mes)
        .order_by(FotoMedicao.eap_codigo, FotoMedicao.id)
        .all()
    )
    for i, f in enumerate(fotos, start=1):
        f.numero = i
    db.commit()


@router.get("/{ano}/{mes}/fotos", response_model=list[FotoOut])
def listar_fotos(
    ano: int,
    mes: int,
    eap_codigo: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(FotoMedicao).filter(FotoMedicao.ano == ano, FotoMedicao.mes == mes)
    if eap_codigo:
        q = q.filter(FotoMedicao.eap_codigo == eap_codigo)
    return q.order_by(FotoMedicao.eap_codigo, FotoMedicao.id).all()


@router.post("/{ano}/{mes}/fotos", response_model=FotoOut, status_code=201)
async def upload_foto(
    ano: int,
    mes: int,
    file: UploadFile = File(...),
    eap_codigo: str = Form(...),
    eap_descricao: Optional[str] = Form(None),
    legenda: Optional[str] = Form(None),
    lancado_por: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(400, "Arquivo sem nome.")

    # Pasta de destino: uploads/fotos/{ano}/{mes:02d}/{eap_codigo}/
    dest_dir = os.path.join(_FOTOS_DIR, str(ano), f"{mes:02d}", eap_codigo)
    os.makedirs(dest_dir, exist_ok=True)

    # Gera nome único preservando extensão
    ext = os.path.splitext(file.filename)[1].lower() or ".bin"
    novo_nome = f"{uuid.uuid4().hex}{ext}"
    dest_path = os.path.join(dest_dir, novo_nome)

    conteudo = await file.read()
    with open(dest_path, "wb") as f:
        f.write(conteudo)

    # Caminho relativo para servir via /uploads/...
    rel_path = os.path.relpath(dest_path, _BASE_UPLOADS).replace("\\", "/")

    foto = FotoMedicao(
        ano=ano,
        mes=mes,
        eap_codigo=eap_codigo,
        eap_descricao=eap_descricao,
        legenda=legenda,
        filename=novo_nome,
        file_path=rel_path,
        tamanho=len(conteudo),
        lancado_por=lancado_por,
    )
    db.add(foto)
    db.commit()
    db.refresh(foto)

    _renumerar(db, ano, mes)
    db.refresh(foto)
    return foto


@router.patch("/{ano}/{mes}/fotos/{foto_id}", response_model=FotoOut)
def atualizar_legenda(
    ano: int,
    mes: int,
    foto_id: int,
    payload: FotoLegendaIn = Body(...),
    db: Session = Depends(get_db),
):
    foto = db.get(FotoMedicao, foto_id)
    if not foto or foto.ano != ano or foto.mes != mes:
        raise HTTPException(404, "Foto não encontrada.")
    foto.legenda = payload.legenda
    db.commit()
    db.refresh(foto)
    return foto


@router.delete("/{ano}/{mes}/fotos/{foto_id}", status_code=204)
def deletar_foto(ano: int, mes: int, foto_id: int, db: Session = Depends(get_db)):
    foto = db.get(FotoMedicao, foto_id)
    if not foto or foto.ano != ano or foto.mes != mes:
        raise HTTPException(404, "Foto não encontrada.")
    # Apaga arquivo do disco
    abs_path = os.path.join(_BASE_UPLOADS, foto.file_path) if foto.file_path else None
    db.delete(foto)
    db.commit()
    if abs_path and os.path.isfile(abs_path):
        try:
            os.remove(abs_path)
        except OSError as e:
            logger.warning("Não foi possível remover arquivo %s: %s", abs_path, e)
    _renumerar(db, ano, mes)


@router.get("/{ano}/{mes}/fotos/{foto_id}/arquivo")
def servir_arquivo(ano: int, mes: int, foto_id: int, db: Session = Depends(get_db)):
    foto = db.get(FotoMedicao, foto_id)
    if not foto or foto.ano != ano or foto.mes != mes:
        raise HTTPException(404, "Foto não encontrada.")
    abs_path = os.path.join(_BASE_UPLOADS, foto.file_path)
    if not os.path.isfile(abs_path):
        raise HTTPException(404, "Arquivo físico não encontrado.")
    return FileResponse(abs_path, filename=foto.filename)
