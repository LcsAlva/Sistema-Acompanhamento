"""Servico SIGEM: status oficial e conciliacao com a LD."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from ..models import LdDocumento, SigemDocumento, SigemHistoricoStatus
from .motor_medicao_service import is_apto, load_config, normalizar_status
from .revisoes_service import registrar_documento_recebido


def _aplicar_campos(doc: SigemDocumento, row: dict, origem: str) -> None:
    doc.revisao = row.get("revisao")
    doc.modificado_em = row.get("modificado_em")
    doc.incluido_em = row.get("incluido_em")
    for i in range(1, 9):
        setattr(doc, f"nivel_{i}", row.get(f"nivel_{i}"))
    doc.origem_arquivo = origem
    doc.data_importacao = datetime.now()


def importar_sigem(db: Session, rows: list[dict], origem_arquivo: str) -> dict:
    existentes = {d.codigo_documento: d for d in db.query(SigemDocumento).all()}
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
            doc = SigemDocumento(codigo_documento=codigo, status=novo_status)
            _aplicar_campos(doc, row, origem_arquivo)
            db.add(doc)
            db.flush()
            existentes[codigo] = doc
            registrar_documento_recebido(
                db,
                codigo_documento=codigo,
                revisao=row.get("revisao"),
                origem="SIGEM",
                arquivo=origem_arquivo,
                status_documento=novo_status,
            )
            novos += 1
            if novo_norm:
                db.add(SigemHistoricoStatus(
                    documento_id=doc.id, status_anterior=None,
                    status_novo=novo_status, arquivo_origem=origem_arquivo,
                ))
                transicoes.append({"codigo": codigo, "de": None, "para": novo_status})
            continue

        antigo_norm = normalizar_status(doc.status)
        antigo_status = doc.status
        houve_mudanca_status = novo_norm != antigo_norm
        rev_result = registrar_documento_recebido(
            db,
            codigo_documento=codigo,
            revisao=row.get("revisao"),
            origem="SIGEM",
            arquivo=origem_arquivo,
            status_documento=novo_status,
        )
        if rev_result["acao"] == "nova_revisao":
            revisoes_detectadas += 1
        _aplicar_campos(doc, row, origem_arquivo)
        doc.status = novo_status
        if houve_mudanca_status:
            db.add(SigemHistoricoStatus(
                documento_id=doc.id, status_anterior=antigo_status,
                status_novo=novo_status, arquivo_origem=origem_arquivo,
            ))
            status_alterados += 1
            transicoes.append({"codigo": codigo, "de": antigo_status, "para": novo_status})
        else:
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


def listar_documentos(db: Session, status: Optional[str] = None, q: Optional[str] = None) -> list[SigemDocumento]:
    query = db.query(SigemDocumento)
    if status:
        query = query.filter(SigemDocumento.status == status)
    if q:
        like = f"%{q}%"
        query = query.filter(SigemDocumento.codigo_documento.ilike(like))
    return query.order_by(SigemDocumento.codigo_documento).all()


def obter_status_atual(db: Session, codigo_documento: str) -> Optional[str]:
    doc = (db.query(SigemDocumento)
           .filter(SigemDocumento.codigo_documento == codigo_documento)
           .first())
    return doc.status if doc else None


def documentos_sem_workflow(db: Session) -> list[SigemDocumento]:
    cfg = load_config()
    return [d for d in db.query(SigemDocumento).all() if is_apto(d.status, cfg)]


def documentos_divergentes(db: Session) -> list[dict]:
    sigem_por_codigo = {s.codigo_documento: s for s in db.query(SigemDocumento).all()}
    agora = datetime.now()
    divergentes: list[dict] = []

    for ld in db.query(LdDocumento).order_by(LdDocumento.codigo_documento).all():
        sigem = sigem_por_codigo.get(ld.codigo_documento)
        if not sigem:
            continue
        status_ld = normalizar_status(ld.status)
        status_sigem = normalizar_status(sigem.status)
        if status_ld == status_sigem:
            continue

        ref = sigem.modificado_em or sigem.data_importacao or ld.data_importacao
        dias = (agora - ref).days if ref else None
        divergentes.append({
            "documento": ld.codigo_documento,
            "disciplina": ld.disciplina,
            "status_ld": ld.status,
            "status_sigem": sigem.status,
            "diferenca": "Divergente",
            "dias_divergentes": max(dias, 0) if dias is not None else None,
            "ultima_atualizacao": sigem.modificado_em,
            "revisao_ld": ld.revisao,
            "revisao_sigem": sigem.revisao,
        })
    return divergentes


def dashboard_conciliacao(db: Session) -> dict:
    cfg = load_config()
    total_ld = db.query(LdDocumento).count()
    sigem_docs = db.query(SigemDocumento).all()
    divergentes = documentos_divergentes(db)
    sigem_por_codigo = {s.codigo_documento: s for s in sigem_docs}

    aptos = 0
    sem_workflow = 0
    for ld in db.query(LdDocumento).all():
        sigem = sigem_por_codigo.get(ld.codigo_documento)
        status_oficial = sigem.status if sigem else ld.status
        if is_apto(status_oficial, cfg):
            aptos += 1
            sem_workflow += 1

    return {
        "total_ld": total_ld,
        "total_sigem": len(sigem_docs),
        "documentos_divergentes": len(divergentes),
        "documentos_aptos": aptos,
        "documentos_sem_workflow": sem_workflow,
        "divergentes": divergentes,
    }


def status_distintos(db: Session) -> list[str]:
    rows = db.query(SigemDocumento.status).distinct().all()
    return sorted({r[0] for r in rows if r[0]})
