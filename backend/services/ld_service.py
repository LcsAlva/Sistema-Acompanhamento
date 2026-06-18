"""Serviço de Integração LD / SIGEM (Módulo 1 — Fase 2A).

Importa a LD (lista de dicts do ld_parser), fazendo upsert por
`codigo_documento` e registrando cada transição de status em
ld_historico_status. Devolve um DIFF da importação (novos, atualizados,
status alterados, sem mudança) — base para a tela de Integração LD.

Substitui a atualização manual do 'LD Histórico Medição'.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from ..models import LdDocumento, LdHistoricoStatus
from .motor_medicao_service import normalizar_status
from .revisoes_service import registrar_documento_recebido


def _aplicar_campos(doc: LdDocumento, row: dict, origem: str) -> None:
    doc.titulo = row.get("titulo")
    doc.disciplina = row.get("disciplina")
    doc.revisao = row.get("revisao")
    doc.a4_equivalente = row.get("a4_equivalente") or 0.0
    doc.data_prevista = row.get("data_prevista")
    doc.data_emissao = row.get("data_emissao")
    doc.data_importacao = datetime.now()
    doc.origem_arquivo = origem


def importar_ld(db: Session, rows: list[dict], origem_arquivo: str) -> dict:
    """Upsert dos documentos da LD + histórico de status. Retorna diff.

    Regra de histórico: grava transição quando o status NORMALIZADO muda
    (inclui criação, quando havia status anterior conhecido). A comparação é
    feita por status normalizado para evitar ruído de espaços/caixa.
    """
    existentes = {d.codigo_documento: d for d in db.query(LdDocumento).all()}

    novos = atualizados = status_alterados = sem_mudanca = 0
    revisoes_detectadas = 0
    transicoes: list[dict] = []

    for row in rows:
        codigo = (row.get("codigo_documento") or "").strip()
        if not codigo:
            continue
        novo_status = row.get("status")
        novo_norm = normalizar_status(novo_status)

        doc = existentes.get(codigo)
        if doc is None:
            doc = LdDocumento(codigo_documento=codigo, status=novo_status)
            _aplicar_campos(doc, row, origem_arquivo)
            db.add(doc)
            db.flush()                       # garante doc.id p/ histórico
            existentes[codigo] = doc
            registrar_documento_recebido(
                db,
                codigo_documento=codigo,
                revisao=row.get("revisao"),
                origem="LD",
                arquivo=origem_arquivo,
                status_documento=novo_status,
            )
            novos += 1
            # registra a entrada inicial como transição (None → status)
            if novo_norm:
                db.add(LdHistoricoStatus(
                    documento_id=doc.id, status_anterior=None,
                    status_novo=novo_status, arquivo_origem=origem_arquivo,
                ))
                transicoes.append({"codigo": codigo, "de": None, "para": novo_status})
            continue

        antigo_norm = normalizar_status(doc.status)
        houve_mudanca_status = novo_norm != antigo_norm
        rev_result = registrar_documento_recebido(
            db,
            codigo_documento=codigo,
            revisao=row.get("revisao"),
            origem="LD",
            arquivo=origem_arquivo,
            status_documento=novo_status,
        )
        if rev_result["acao"] == "nova_revisao":
            revisoes_detectadas += 1
        _aplicar_campos(doc, row, origem_arquivo)
        if houve_mudanca_status:
            db.add(LdHistoricoStatus(
                documento_id=doc.id, status_anterior=doc.status,
                status_novo=novo_status, arquivo_origem=origem_arquivo,
            ))
            doc.status = novo_status
            status_alterados += 1
            transicoes.append({"codigo": codigo, "de": antigo_norm, "para": novo_status})
        else:
            doc.status = novo_status        # mantém a grafia mais recente
            atualizados += 1

    sem_mudanca = max(0, len(rows) - novos - status_alterados - atualizados)
    db.commit()
    return {
        "origem_arquivo": origem_arquivo,
        "total_linhas": len(rows),
        "novos": novos,
        "atualizados": atualizados,
        "status_alterados": status_alterados,
        "sem_mudanca": sem_mudanca,
        "revisoes_detectadas": revisoes_detectadas,
        "transicoes": transicoes,
    }


def listar_documentos(db: Session, disciplina: Optional[str] = None,
                      status: Optional[str] = None, q: Optional[str] = None) -> list[LdDocumento]:
    query = db.query(LdDocumento)
    if disciplina:
        query = query.filter(LdDocumento.disciplina == disciplina)
    if status:
        query = query.filter(LdDocumento.status == status)
    if q:
        like = f"%{q}%"
        query = query.filter(
            LdDocumento.codigo_documento.ilike(like) | LdDocumento.titulo.ilike(like)
        )
    return query.order_by(LdDocumento.codigo_documento).all()


def historico(db: Session, documento_id: int) -> list[LdHistoricoStatus]:
    return (db.query(LdHistoricoStatus)
            .filter(LdHistoricoStatus.documento_id == documento_id)
            .order_by(LdHistoricoStatus.data_alteracao).all())


def disciplinas_distintas(db: Session) -> list[str]:
    rows = db.query(LdDocumento.disciplina).distinct().all()
    return sorted({r[0] for r in rows if r[0]})


def status_distintos(db: Session) -> list[str]:
    rows = db.query(LdDocumento.status).distinct().all()
    return sorted({r[0] for r in rows if r[0]})
