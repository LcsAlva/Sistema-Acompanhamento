"""
Fase 3 — Lista de Documentos de Engenharia
==========================================
Gerencia a lista de documentos (LD) e calcula automaticamente
o percentual de avanço do item EAP 2.1.1.

Fórmula de progresso (por documento):
  EM_ELABORACAO    →  0 % do peso
  EM_ANALISE       → 60 % do peso
  COM_COMENTARIOS  → 60 % do peso  (emitido, mas aguardando revisão)
  SEM_COMENTARIOS  →100 % do peso  (aprovado sem ressalvas)
  APROVADO         →100 % do peso
"""

from __future__ import annotations

import io
import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import DocumentoEngenharia
from ..schemas import (
    DocumentoIn, DocumentoUpdate, DocumentoOut,
    Progresso211Out, DocumentoImportResultado,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documentos", tags=["documentos"])

# ── fator de contribuição por status ──────────────────────────────────
_FATOR: dict[str, float] = {
    "EM_ELABORACAO":   0.0,
    "EM_ANALISE":      0.6,
    "COM_COMENTARIOS": 0.6,
    "SEM_COMENTARIOS": 1.0,
    "APROVADO":        1.0,
}

_STATUS_VALIDOS = set(_FATOR.keys())


def _calcular_progresso(docs: list[DocumentoEngenharia]) -> Progresso211Out:
    """Calcula o % de avanço de 2.1.1 a partir da lista de documentos."""
    contadores = {s: 0 for s in _STATUS_VALIDOS}
    peso_total = 0.0
    peso_realizado = 0.0

    for d in docs:
        st = d.status or "EM_ELABORACAO"
        contadores[st] = contadores.get(st, 0) + 1
        peso_total += d.peso or 1.0
        peso_realizado += (d.peso or 1.0) * _FATOR.get(st, 0.0)

    pct = (peso_realizado / peso_total) if peso_total > 0 else 0.0

    return Progresso211Out(
        pct=round(pct, 6),
        pct_fmt=f"{pct * 100:.1f}%",
        total_docs=len(docs),
        em_elaboracao=contadores["EM_ELABORACAO"],
        em_analise=contadores["EM_ANALISE"],
        com_comentarios=contadores["COM_COMENTARIOS"],
        sem_comentarios=contadores["SEM_COMENTARIOS"],
        aprovados=contadores["APROVADO"],
        peso_total=round(peso_total, 4),
        peso_realizado=round(peso_realizado, 4),
    )


# ── endpoints ─────────────────────────────────────────────────────────

@router.get("/progresso-211", response_model=Progresso211Out)
def get_progresso_211(db: Session = Depends(get_db)):
    """Retorna o % calculado para o item EAP 2.1.1 baseado nos documentos."""
    docs = db.query(DocumentoEngenharia).all()
    return _calcular_progresso(docs)


@router.get("", response_model=list[DocumentoOut])
def listar_documentos(
    disciplina: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    q: Optional[str] = Query(None, description="Busca livre em código e título"),
    db: Session = Depends(get_db),
):
    query = db.query(DocumentoEngenharia)
    if disciplina:
        query = query.filter(DocumentoEngenharia.disciplina == disciplina)
    if status:
        query = query.filter(DocumentoEngenharia.status == status)
    if q:
        like = f"%{q}%"
        query = query.filter(
            DocumentoEngenharia.codigo.ilike(like) |
            DocumentoEngenharia.titulo.ilike(like)
        )
    return query.order_by(DocumentoEngenharia.codigo).all()


@router.post("", response_model=DocumentoOut, status_code=201)
def criar_documento(payload: DocumentoIn, db: Session = Depends(get_db)):
    if payload.status and payload.status not in _STATUS_VALIDOS:
        raise HTTPException(400, f"Status inválido: {payload.status}. Válidos: {sorted(_STATUS_VALIDOS)}")
    if db.query(DocumentoEngenharia).filter_by(codigo=payload.codigo).first():
        raise HTTPException(409, f"Documento com código '{payload.codigo}' já existe.")
    doc = DocumentoEngenharia(**payload.model_dump())
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@router.put("/{doc_id}", response_model=DocumentoOut)
def atualizar_documento(doc_id: int, payload: DocumentoUpdate, db: Session = Depends(get_db)):
    doc = db.get(DocumentoEngenharia, doc_id)
    if not doc:
        raise HTTPException(404, "Documento não encontrado.")
    if payload.status and payload.status not in _STATUS_VALIDOS:
        raise HTTPException(400, f"Status inválido: {payload.status}")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(doc, k, v)
    db.commit()
    db.refresh(doc)
    return doc


@router.patch("/{doc_id}/status", response_model=DocumentoOut)
def alterar_status(
    doc_id: int,
    novo_status: str = Query(..., description="Novo status do documento"),
    emitido_em: Optional[date] = Query(None),
    aprovado_em: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    if novo_status not in _STATUS_VALIDOS:
        raise HTTPException(400, f"Status inválido: {novo_status}")
    doc = db.get(DocumentoEngenharia, doc_id)
    if not doc:
        raise HTTPException(404, "Documento não encontrado.")
    doc.status = novo_status
    if emitido_em:
        doc.emitido_em = emitido_em
    elif novo_status == "EM_ANALISE" and not doc.emitido_em:
        doc.emitido_em = date.today()
    if aprovado_em:
        doc.aprovado_em = aprovado_em
    elif novo_status in ("SEM_COMENTARIOS", "APROVADO") and not doc.aprovado_em:
        doc.aprovado_em = date.today()
    db.commit()
    db.refresh(doc)
    return doc


@router.delete("/{doc_id}", status_code=204)
def deletar_documento(doc_id: int, db: Session = Depends(get_db)):
    doc = db.get(DocumentoEngenharia, doc_id)
    if not doc:
        raise HTTPException(404, "Documento não encontrado.")
    db.delete(doc)
    db.commit()


@router.post("/importar-excel", response_model=DocumentoImportResultado)
async def importar_excel(
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Importa documentos de uma planilha Excel.
    Colunas esperadas (case-insensitive, ordem livre):
      codigo*, titulo*, disciplina, tipo_doc, revisao_atual,
      status, emitido_em (dd/mm/aaaa), aprovado_em, peso, observacao
    * obrigatórias
    """
    try:
        import openpyxl
    except ImportError:
        raise HTTPException(500, "openpyxl não instalado.")

    conteudo = await arquivo.read()
    try:
        wb = openpyxl.load_workbook(io.BytesIO(conteudo), data_only=True)
    except Exception as e:
        raise HTTPException(400, f"Erro ao ler o arquivo Excel: {e}")

    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < 2:
        raise HTTPException(400, "Planilha vazia ou sem dados após o cabeçalho.")

    # Mapeia cabeçalho → índice de coluna (case-insensitive, strip)
    header = [str(c).strip().lower() if c else "" for c in rows[0]]
    col = {h: i for i, h in enumerate(header)}

    def _get(row, name: str, default=None):
        i = col.get(name.lower())
        if i is None:
            return default
        v = row[i]
        return v if v is not None else default

    def _parse_date(v) -> Optional[date]:
        if v is None:
            return None
        if hasattr(v, "date"):
            return v.date()
        s = str(v).strip()
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                from datetime import datetime as _dt
                return _dt.strptime(s, fmt).date()
            except ValueError:
                continue
        return None

    inseridos = atualizados = 0
    erros: list[str] = []

    for i, row in enumerate(rows[1:], start=2):
        codigo = str(_get(row, "codigo") or "").strip()
        titulo = str(_get(row, "titulo") or "").strip()
        if not codigo:
            continue
        if not titulo:
            erros.append(f"Linha {i}: 'titulo' obrigatório.")
            continue

        status_raw = str(_get(row, "status") or "EM_ELABORACAO").strip().upper().replace(" ", "_")
        if status_raw not in _STATUS_VALIDOS:
            status_raw = "EM_ELABORACAO"

        try:
            peso_val = float(_get(row, "peso") or 1.0)
        except (ValueError, TypeError):
            peso_val = 1.0

        existente = db.query(DocumentoEngenharia).filter_by(codigo=codigo).first()
        dados = dict(
            titulo=titulo,
            disciplina=str(_get(row, "disciplina") or "").strip() or None,
            tipo_doc=str(_get(row, "tipo_doc") or "").strip() or None,
            revisao_atual=str(_get(row, "revisao_atual") or "").strip() or None,
            status=status_raw,
            emitido_em=_parse_date(_get(row, "emitido_em")),
            aprovado_em=_parse_date(_get(row, "aprovado_em")),
            peso=peso_val,
            observacao=str(_get(row, "observacao") or "").strip() or None,
        )
        if existente:
            for k, v in dados.items():
                setattr(existente, k, v)
            atualizados += 1
        else:
            db.add(DocumentoEngenharia(codigo=codigo, **dados))
            inseridos += 1

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Erro ao salvar: {e}")

    return DocumentoImportResultado(inseridos=inseridos, atualizados=atualizados, erros=erros)
