"""Gestao de revisoes de documentos LD/SIGEM e analise de impacto."""
from __future__ import annotations

import json
from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from ..models import ControleDocumento, DocumentoRevisao, EventoRevisaoDocumento, LdDocumento


STATUS_CONTROLE_REVISAO = "Revisar impacto da revisao"
STATUS_EVENTO_PENDENTE = "Pendente analise"


def _norm(value: str | None) -> str:
    return (value or "").strip()


def _controles_por_documento(db: Session, codigo_documento: str) -> list[ControleDocumento]:
    return (
        db.query(ControleDocumento)
        .filter(ControleDocumento.documento_origem == codigo_documento)
        .order_by(ControleDocumento.codigo_controle)
        .all()
    )


def registrar_documento_recebido(
    db: Session,
    *,
    codigo_documento: str,
    revisao: str | None,
    origem: str,
    arquivo: str | None = None,
    status_documento: str | None = None,
    observacao_revisao: str | None = None,
) -> dict:
    """Registra documento/revisao e cria evento quando a revisao for nova.

    Nao altera pedido, quantitativo, material, montagem ou medicao/report.
    Apenas marca controles vinculados para analise manual.
    """
    codigo = _norm(codigo_documento)
    rev = _norm(revisao) or "SEM_REVISAO"
    if not codigo:
        return {"acao": "ignorado", "evento": None, "controles_afetados": 0}

    existente_mesma_rev = (
        db.query(DocumentoRevisao)
        .filter(
            DocumentoRevisao.codigo_documento == codigo,
            DocumentoRevisao.revisao == rev,
        )
        .first()
    )
    if existente_mesma_rev:
        existente_mesma_rev.status_documento = status_documento or existente_mesma_rev.status_documento
        existente_mesma_rev.origem = origem or existente_mesma_rev.origem
        existente_mesma_rev.arquivo = arquivo or existente_mesma_rev.arquivo
        existente_mesma_rev.observacao_revisao = observacao_revisao or existente_mesma_rev.observacao_revisao
        existente_mesma_rev.atualizado_em = datetime.now()
        return {"acao": "mesma_revisao", "evento": None, "controles_afetados": 0}

    vigente = (
        db.query(DocumentoRevisao)
        .filter(
            DocumentoRevisao.codigo_documento == codigo,
            DocumentoRevisao.revisao_vigente.is_(True),
        )
        .order_by(DocumentoRevisao.data_recebimento.desc())
        .first()
    )

    nova = DocumentoRevisao(
        codigo_documento=codigo,
        revisao=rev,
        revisao_vigente=True,
        status_documento="Vigente",
        status_classificacao="Pendente de classificacao",
        origem=origem,
        arquivo=arquivo,
        observacao_revisao=observacao_revisao,
        substitui_revisao=vigente.revisao if vigente else None,
    )
    db.add(nova)

    if vigente is None:
        return {"acao": "novo_documento", "evento": None, "controles_afetados": 0}

    vigente.revisao_vigente = False
    vigente.status_documento = "Substituido"
    vigente.atualizado_em = datetime.now()

    controles = _controles_por_documento(db, codigo)
    codigos_controle = []
    for controle in controles:
        codigos_controle.append(controle.codigo_controle)
        controle.status_controle = STATUS_CONTROLE_REVISAO
        controle.atualizado_em = datetime.now()

    evento = EventoRevisaoDocumento(
        id_evento_revisao=f"REV-{datetime.now():%Y%m%d%H%M%S}-{uuid4().hex[:8]}",
        codigo_documento=codigo,
        revisao_anterior=vigente.revisao,
        revisao_nova=rev,
        controles_afetados=json.dumps(codigos_controle, ensure_ascii=False),
        status_analise=STATUS_EVENTO_PENDENTE,
    )
    db.add(evento)
    return {"acao": "nova_revisao", "evento": evento, "controles_afetados": len(controles)}


def listar_eventos(db: Session, status: str | None = None, q: str | None = None) -> list[dict]:
    query = db.query(EventoRevisaoDocumento)
    if status:
        query = query.filter(EventoRevisaoDocumento.status_analise == status)
    if q:
        like = f"%{q}%"
        query = query.filter(EventoRevisaoDocumento.codigo_documento.ilike(like))

    eventos = query.order_by(EventoRevisaoDocumento.data_deteccao.desc()).all()
    linhas: list[dict] = []
    for evento in eventos:
        controles = _controles_por_documento(db, evento.codigo_documento)
        if not controles:
            linhas.append(_linha_evento(evento, None))
            continue
        for controle in controles:
            linhas.append(_linha_evento(evento, controle))
    return linhas


def _linha_evento(evento: EventoRevisaoDocumento, controle: ControleDocumento | None) -> dict:
    alertas = []
    if controle:
        if controle.tem_pedido or controle.numero_pedido:
            alertas.append("Existem pedidos emitidos com base em revisao anterior.")
        if controle.tem_material:
            alertas.append("Ha material solicitado/recebido vinculado a revisao anterior.")
        if controle.tem_montagem:
            alertas.append("Ha montagem/execucao registrada vinculada a revisao anterior.")
        if controle.entrou_medicao_report:
            alertas.append("Este documento/controle ja foi considerado em report de medicao.")

    return {
        "id": evento.id,
        "id_evento_revisao": evento.id_evento_revisao,
        "codigo_documento": evento.codigo_documento,
        "revisao_anterior": evento.revisao_anterior,
        "revisao_nova": evento.revisao_nova,
        "data_deteccao": evento.data_deteccao,
        "controle_aplicavel": controle.controle_aplicavel if controle else None,
        "setor": controle.setor if controle else None,
        "area": controle.area if controle else None,
        "codigo_controle_afetado": controle.codigo_controle if controle else None,
        "status_controle": controle.status_controle if controle else None,
        "status_analise": evento.status_analise,
        "impacto_informado": evento.impacto_informado,
        "acao_necessaria": evento.acao_necessaria,
        "observacao_impacto": evento.observacao_impacto,
        "alertas": alertas,
        "pedido": {
            "numero_pedido": controle.numero_pedido if controle else None,
            "status_pedido": controle.status_pedido if controle else None,
            "revisao_documento_usada": controle.revisao_documento_usada if controle else None,
            "data_pedido": controle.data_pedido if controle else None,
        } if controle and (controle.tem_pedido or controle.numero_pedido) else None,
        "variacao": {
            "item_controlavel": evento.item_controlavel,
            "quantidade_anterior": evento.quantidade_anterior,
            "quantidade_nova": evento.quantidade_nova,
            "diferenca_quantidade": evento.diferenca_quantidade,
            "unidade": evento.unidade,
            "tipo_variacao": evento.tipo_variacao,
        },
    }


def atualizar_analise(db: Session, evento_id: int, payload) -> EventoRevisaoDocumento:
    evento = db.query(EventoRevisaoDocumento).filter(EventoRevisaoDocumento.id == evento_id).first()
    if not evento:
        raise ValueError("Evento de revisao nao encontrado")

    for campo in (
        "status_analise",
        "analisado_por",
        "impacto_informado",
        "acao_necessaria",
        "observacao_impacto",
        "item_controlavel",
        "quantidade_anterior",
        "quantidade_nova",
        "unidade",
        "tipo_variacao",
        "acao_pedido",
    ):
        if hasattr(payload, campo):
            valor = getattr(payload, campo)
            if valor is not None:
                setattr(evento, campo, valor)

    impacto = _norm(getattr(payload, "impacto_informado", None))
    evento.impacto_quantitativo = impacto == "Impactou quantitativo"
    evento.impacto_material = impacto == "Impactou material"
    evento.impacto_montagem = impacto == "Impactou montagem"
    evento.impacto_medicao_report = impacto == "Impactou medicao/report"

    qa = evento.quantidade_anterior
    qn = evento.quantidade_nova
    evento.diferenca_quantidade = (qn - qa) if isinstance(qa, (int, float)) and isinstance(qn, (int, float)) else None
    evento.data_analise = datetime.now()
    evento.atualizado_em = datetime.now()

    if evento.status_analise in {"Sem impacto", "Revisao tratada"}:
        novo_status_controle = "Revisado sem impacto" if evento.status_analise == "Sem impacto" else "Revisado com impacto"
        for controle in _controles_por_documento(db, evento.codigo_documento):
            if controle.status_controle == STATUS_CONTROLE_REVISAO:
                controle.status_controle = novo_status_controle
                controle.atualizado_em = datetime.now()

    db.commit()
    db.refresh(evento)
    return evento


def listar_controles(db: Session, documento: str | None = None, q: str | None = None) -> list[ControleDocumento]:
    query = db.query(ControleDocumento)
    if documento:
        query = query.filter(ControleDocumento.documento_origem == documento)
    if q:
        like = f"%{q}%"
        query = query.filter(
            ControleDocumento.codigo_controle.ilike(like)
            | ControleDocumento.documento_origem.ilike(like)
            | ControleDocumento.controle_aplicavel.ilike(like)
            | ControleDocumento.setor.ilike(like)
            | ControleDocumento.area.ilike(like)
        )
    return query.order_by(ControleDocumento.documento_origem, ControleDocumento.codigo_controle).all()


def criar_controle(db: Session, payload) -> ControleDocumento:
    documento = _norm(payload.documento_origem)
    if not documento:
        raise ValueError("Documento de origem e obrigatorio")

    ld = db.query(LdDocumento).filter(LdDocumento.codigo_documento == documento).first()
    revisao = payload.revisao_documento or (ld.revisao if ld else None)
    codigo = _norm(payload.codigo_controle)
    if not codigo:
        total_doc = db.query(ControleDocumento).filter(ControleDocumento.documento_origem == documento).count()
        codigo = f"CTRL-{documento}-{total_doc + 1:03d}"

    existente = db.query(ControleDocumento).filter(ControleDocumento.codigo_controle == codigo).first()
    if existente:
        raise ValueError("Ja existe controle com este codigo")

    controle = ControleDocumento(
        codigo_controle=codigo,
        documento_origem=documento,
        revisao_documento=revisao,
        controle_aplicavel=payload.controle_aplicavel,
        setor=payload.setor,
        area=payload.area,
        status_controle=payload.status_controle or "Aberto",
        tem_pedido=bool(payload.tem_pedido),
        numero_pedido=payload.numero_pedido,
        status_pedido=payload.status_pedido,
        revisao_documento_usada=payload.revisao_documento_usada or revisao,
        data_pedido=payload.data_pedido,
        tem_material=bool(payload.tem_material),
        tem_montagem=bool(payload.tem_montagem),
        entrou_medicao_report=bool(payload.entrou_medicao_report),
    )
    db.add(controle)
    db.commit()
    db.refresh(controle)
    return controle
