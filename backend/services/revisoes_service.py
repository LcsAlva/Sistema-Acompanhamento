"""Gestao de revisoes de documentos LD/SIGEM e analise de impacto."""
from __future__ import annotations

import json
import os
import re
import unicodedata
from pathlib import Path
from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from ..models import (
    ControleDocumento,
    ControleQuantitativo,
    DocumentoRevisao,
    EventoRevisaoDocumento,
    LdDocumento,
    SigemDocumento,
)


STATUS_CONTROLE_REVISAO = "Revisar impacto da revisao"
STATUS_EVENTO_PENDENTE = "Pendente analise"


def _norm(value: str | None) -> str:
    return (value or "").strip()


def _norm_upper(value: str | None) -> str:
    texto = unicodedata.normalize("NFKD", value or "")
    return "".join(c for c in texto if not unicodedata.combining(c)).upper()


def _titulo_sigem(doc: SigemDocumento) -> str:
    for value in (
        doc.nivel_8, doc.nivel_7, doc.nivel_6, doc.nivel_5,
        doc.nivel_4, doc.nivel_3, doc.nivel_2, doc.nivel_1,
    ):
        if value:
            return value
    return ""


def _area_sigem(doc: SigemDocumento) -> str:
    return doc.nivel_4 or doc.nivel_3 or doc.nivel_2 or "Geral"


def _status_emitido_postado(status: str | None) -> bool:
    status_norm = _norm_upper(status)
    return bool(status_norm) and status_norm != "EM ELABORACAO"


def _eh_documentacao_tecnica_sigem(doc: SigemDocumento) -> bool:
    return _norm_upper(doc.nivel_1) == "DOCUMENTACAO TECNICA"


def _codigos_documentacao_tecnica(db: Session) -> set[str]:
    return {
        doc.codigo_documento
        for doc in db.query(SigemDocumento).all()
        if doc.codigo_documento and _eh_documentacao_tecnica_sigem(doc)
    }


def tipo_controle_documento(
    *,
    codigo_documento: str | None,
    titulo: str | None,
    disciplina: str | None,
) -> str:
    """Classifica um documento no tipo de controle padrao.

    Mantem a regra em um unico lugar para cadastro manual, lote e revisoes
    futuras de novos documentos emitidos.
    """
    codigo = _norm_upper(codigo_documento)
    titulo_norm = _norm_upper(titulo)
    disciplina_norm = _norm_upper(disciplina)

    if re.match(r"^LI-.*-293-", codigo) or "SUPORTE" in titulo_norm or "SUPORTES" in titulo_norm:
        return "Tubulacao - Suportes"
    if (
        re.match(r"^(IS|SP)-", codigo)
        or re.search(r"-[^-]*-200-", codigo)
        or "ISOMETR" in titulo_norm
        or "SPOOL" in titulo_norm
        or "TUBULA" in disciplina_norm
    ):
        return "Tubulacao - Tubos e conexoes"

    gatilhos_civil = ("CONCRETO", "ARMADURA", "ARMACAO", "METALICA", "FUNDA", "FORMA", "BASE", "BLOCO", "PLATAFORMA")
    if "CIVIL" in disciplina_norm or any(token in titulo_norm for token in gatilhos_civil):
        if any(token in titulo_norm for token in ("ARMADURA", "ARMACAO", "FORMAS E ARMADURAS", "FORMA E ARM")):
            return "Construcao civil - Armadura"
        if any(token in titulo_norm for token in ("METALICA", "ESTRUTURA METAL", "PLATAFORMA")):
            return "Construcao civil - Estrutura metalica"
        if any(token in titulo_norm for token in ("CONCRETO", "FUNDA", "BASE", "BLOCO")):
            return "Construcao civil - m3 de concreto"
        return "Construcao civil - Geral"

    disciplina_label = _norm(disciplina).title() or "Geral"
    return f"{disciplina_label} - Quantitativo geral"


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
    codigos_tecnicos = _codigos_documentacao_tecnica(db)
    if not codigos_tecnicos:
        return []
    query = query.filter(ControleDocumento.documento_origem.in_(codigos_tecnicos))
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
        codigo = _proximo_codigo_controle(db, documento)

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


def _proximo_codigo_controle(db: Session, documento: str) -> str:
    total_doc = db.query(ControleDocumento).filter(ControleDocumento.documento_origem == documento).count()
    idx = total_doc + 1
    while True:
        codigo = f"CTRL-{documento}-{idx:03d}"
        existente = db.query(ControleDocumento).filter(ControleDocumento.codigo_controle == codigo).first()
        if not existente:
            return codigo
        idx += 1


def _docs_classificaveis_sigem(db: Session) -> list[dict]:
    lds = {doc.codigo_documento: doc for doc in db.query(LdDocumento).all()}
    docs = []
    for sigem in db.query(SigemDocumento).all():
        if not _eh_documentacao_tecnica_sigem(sigem) or not _status_emitido_postado(sigem.status):
            continue
        ld = lds.get(sigem.codigo_documento)
        docs.append({
            "codigo_documento": sigem.codigo_documento,
            "titulo": (ld.titulo if ld else None) or _titulo_sigem(sigem),
            "disciplina": (ld.disciplina if ld else None) or _area_sigem(sigem),
            "revisao": sigem.revisao or (ld.revisao if ld else None),
            "origem": "SIGEM",
        })
    return docs


def _docs_classificaveis_ld(db: Session) -> list[dict]:
    return [
        {
            "codigo_documento": doc.codigo_documento,
            "titulo": doc.titulo,
            "disciplina": doc.disciplina or "Geral",
            "revisao": doc.revisao,
            "origem": "LD",
        }
        for doc in db.query(LdDocumento).all()
    ]


def classificar_controles_pendentes(db: Session, fonte: str = "sigem") -> dict:
    """Cria controles para documentos classificaveis que ainda nao possuem controle.

    A operacao e idempotente: documentos que ja possuem qualquer controle sao
    preservados, permitindo rodar apos cada nova importacao LD/SIGEM.
    """
    fonte_norm = (fonte or "sigem").lower()
    docs_by_codigo: dict[str, dict] = {}
    if fonte_norm in {"sigem", "todos"}:
        for doc in _docs_classificaveis_sigem(db):
            docs_by_codigo[doc["codigo_documento"]] = doc
    if fonte_norm in {"ld", "todos"}:
        for doc in _docs_classificaveis_ld(db):
            docs_by_codigo.setdefault(doc["codigo_documento"], doc)
    if fonte_norm not in {"sigem", "ld", "todos"}:
        raise ValueError("Fonte invalida. Use sigem, ld ou todos.")

    existentes = {
        row[0]
        for row in db.query(ControleDocumento.documento_origem).distinct().all()
    }
    criados_por_tipo: dict[str, int] = {}
    criados = []

    for codigo_documento in sorted(docs_by_codigo):
        if codigo_documento in existentes:
            continue
        doc = docs_by_codigo[codigo_documento]
        tipo = tipo_controle_documento(
            codigo_documento=doc["codigo_documento"],
            titulo=doc.get("titulo"),
            disciplina=doc.get("disciplina"),
        )
        controle = ControleDocumento(
            codigo_controle=_proximo_codigo_controle(db, codigo_documento),
            documento_origem=codigo_documento,
            revisao_documento=doc.get("revisao"),
            controle_aplicavel=tipo,
            setor="Engenharia",
            area=doc.get("disciplina") or "Geral",
            status_controle="Aberto",
            tem_pedido=False,
            tem_material=False,
            tem_montagem=False,
            entrou_medicao_report=False,
        )
        db.add(controle)
        existentes.add(codigo_documento)
        criados.append(controle)
        criados_por_tipo[tipo] = criados_por_tipo.get(tipo, 0) + 1

    db.commit()
    for controle in criados:
        db.refresh(controle)

    return {
        "fonte": fonte_norm,
        "candidatos": len(docs_by_codigo),
        "criados": len(criados),
        "ignorados_ja_classificados": len(docs_by_codigo) - len(criados),
        "por_tipo": criados_por_tipo,
    }


def _unidade_principal(tipo: str | None) -> str:
    tipo_norm = _norm_upper(tipo)
    if "M3 DE CONCRETO" in tipo_norm:
        return "m3"
    if "ARMADURA" in tipo_norm or "ESTRUTURA METALICA" in tipo_norm:
        return "kg"
    if "TUBOS" in tipo_norm:
        return "m"
    if "SUPORTE" in tipo_norm:
        return "un"
    return "doc"


def _inferir_isometrico(codigo: str | None, titulo: str | None) -> str:
    codigo_norm = _norm(codigo)
    titulo_norm = _norm(titulo)
    if _norm_upper(codigo_norm).startswith(("IS-", "SP-")):
        return codigo_norm
    match = re.search(r"\b(?:IS|ISO|ISOMETRICO)[-\s:]*([A-Z0-9.-]+)", _norm_upper(titulo_norm))
    return match.group(0) if match else "Nao informado"


def _inferir_linha(codigo: str | None, titulo: str | None) -> str:
    texto = f"{titulo or ''}"
    for padrao in (
        r"\bLINHA\s*[:\-]?\s*([A-Z0-9./-]+)",
        r"\bLINE\s*[:\-]?\s*([A-Z0-9./-]+)",
        r"\b\d{1,2}['\"]?-[A-Z0-9]{1,8}-\d{3,5}-[A-Z0-9-]+",
    ):
        match = re.search(padrao, _norm_upper(texto))
        if match:
            return match.group(1) if match.groups() else match.group(0)
    return "Nao informado"


def _status_geral(controle: ControleDocumento | None, classificado: bool, revisao_pendente: bool) -> str:
    if revisao_pendente:
        return "Revisar impacto"
    if not classificado:
        return "Pendente classificacao"
    if controle and controle.status_controle:
        return controle.status_controle
    return "Classificado"


def listar_controle_completo(db: Session) -> dict:
    lds = {doc.codigo_documento: doc for doc in db.query(LdDocumento).all()}
    sigems = {doc.codigo_documento: doc for doc in db.query(SigemDocumento).all()}
    eventos_pendentes = {
        evento.codigo_documento
        for evento in db.query(EventoRevisaoDocumento).all()
        if evento.status_analise not in {"Sem impacto", "Revisao tratada", "Cancelado"}
    }
    quant_por_controle: dict[int, dict[str, float]] = {}
    for item in db.query(ControleQuantitativo).all():
        unidade = _normaliza_unidade(item.unidade)
        bucket = quant_por_controle.setdefault(item.controle_id, {})
        bucket[unidade] = bucket.get(unidade, 0.0) + float(item.quantidade or 0)

    linhas = []
    for controle in listar_controles(db):
        ld = lds.get(controle.documento_origem)
        sigem = sigems.get(controle.documento_origem)
        titulo = (ld.titulo if ld else None) or (_titulo_sigem(sigem) if sigem else None) or ""
        disciplina = (ld.disciplina if ld else None) or (_area_sigem(sigem) if sigem else None) or "Nao informado"
        area = controle.area or disciplina or "Nao informado"
        unidade = _unidade_principal(controle.controle_aplicavel)
        qtd = quant_por_controle.get(controle.id, {}).get(unidade)
        revisao_pendente = controle.documento_origem in eventos_pendentes or controle.status_controle == STATUS_CONTROLE_REVISAO
        linha = {
            "area": area,
            "isometrico": _inferir_isometrico(controle.documento_origem, titulo),
            "linha": _inferir_linha(controle.documento_origem, titulo),
            "codigo_documento": controle.documento_origem,
            "titulo_documento": titulo,
            "revisao_vigente": controle.revisao_documento or (sigem.revisao if sigem else None) or (ld.revisao if ld else None),
            "disciplina": disciplina,
            "controle_aplicavel": controle.controle_aplicavel or "Nao informado",
            "codigo_controle": controle.codigo_controle,
            "responsavel": controle.setor or "Nao informado",
            "status_controle": controle.status_controle or "Aberto",
            "quantidade_prevista": round(qtd, 3) if qtd is not None else None,
            "unidade": unidade,
            "pedido_gerado": "Sim" if controle.tem_pedido or controle.numero_pedido else "Nao",
            "material_solicitado": "Sim" if controle.tem_material else "Nao",
            "material_disponivel": "Nao informado",
            "montagem": "Sim" if controle.tem_montagem else "Nao",
            "medicao_report": "Sim" if controle.entrou_medicao_report else "Nao",
            "status_sigem": sigem.status if sigem else "Nao informado",
            "status_classificacao": "Classificado",
            "status_geral": _status_geral(controle, True, revisao_pendente),
            "observacao": "Quantidade extraida de PDF, revisar" if qtd is not None else "Sem quantitativo extraido",
        }
        linhas.append(linha)

    linhas.sort(key=lambda item: (item["area"], item["isometrico"], item["linha"], item["codigo_documento"], item["codigo_controle"]))
    return {
        "linhas": linhas,
        "resumo": {
            "controles": len(linhas),
            "documentos": len({linha["codigo_documento"] for linha in linhas}),
            "areas": len({linha["area"] for linha in linhas}),
            "isometricos": len({linha["isometrico"] for linha in linhas if linha["isometrico"] != "Nao informado"}),
        },
    }


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _pdfs_index() -> list[Path]:
    root = _workspace_root()
    return list(root.rglob("*.pdf")) + list(root.rglob("*.PDF"))


def _normaliza_codigo_arquivo(value: str | None) -> str:
    return re.sub(r"[^A-Z0-9]", "", _norm_upper(value))


def _localizar_pdf_documento(codigo_documento: str, pdfs: list[Path] | None = None) -> Path | None:
    codigo_norm = _normaliza_codigo_arquivo(codigo_documento)
    if not codigo_norm:
        return None
    melhor: Path | None = None
    for pdf in (pdfs if pdfs is not None else _pdfs_index()):
        nome_norm = _normaliza_codigo_arquivo(pdf.stem)
        if codigo_norm in nome_norm:
            melhor = pdf
            if "=" in pdf.name or "[" in str(pdf.parent):
                return pdf
    return melhor


def _texto_pdf(path: Path, max_paginas: int = 12) -> str:
    try:
        from pypdf import PdfReader
    except Exception as exc:  # pragma: no cover - depende do ambiente
        raise RuntimeError("Dependencia pypdf nao instalada") from exc

    reader = PdfReader(str(path))
    partes = []
    for page in reader.pages[:max_paginas]:
        try:
            partes.append(page.extract_text() or "")
        except Exception:
            continue
    return "\n".join(partes)


_QTD_RE = re.compile(
    r"(?<![A-Za-z])(?P<qtd>\d{1,3}(?:[.\s]\d{3})*(?:,\d+)?|\d+(?:[.,]\d+)?)\s*"
    r"(?P<un>m3|m³|kg|m|un|und|unid|pç|pc|pcs)\b",
    re.IGNORECASE,
)


def _numero_ptbr(value: str) -> float:
    texto = value.replace(" ", "")
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    return float(texto)


def _normaliza_unidade(value: str) -> str:
    unidade = _norm_upper(value).lower()
    if unidade in {"m3", "m³"}:
        return "m3"
    if unidade == "kg":
        return "kg"
    if unidade == "m":
        return "m"
    if unidade in {"un", "und", "unid", "pc", "pcs", "pç"}:
        return "un"
    return unidade


def _extrair_quantidades_texto(texto: str, unidade_preferida: str | None = None) -> list[dict]:
    linhas = []
    preferida = _normaliza_unidade(unidade_preferida or "")
    if not preferida or preferida == "doc":
        return linhas
    texto_plano = re.sub(r"\s+", " ", texto)
    for match in _QTD_RE.finditer(texto_plano):
        unidade = _normaliza_unidade(match.group("un"))
        if preferida and preferida != "doc" and unidade != preferida:
            continue
        try:
            quantidade = _numero_ptbr(match.group("qtd"))
        except ValueError:
            continue
        if quantidade <= 0:
            continue
        if unidade == "m" and quantidade > 1000:
            continue
        if unidade == "kg" and quantidade > 100000:
            continue
        if unidade == "m3" and quantidade > 10000:
            continue
        if unidade == "un" and quantidade > 10000:
            continue
        inicio = max(match.start() - 80, 0)
        fim = min(match.end() + 100, len(texto_plano))
        evidencia = texto_plano[inicio:fim].strip()
        linhas.append({
            "quantidade": quantidade,
            "unidade": unidade,
            "evidencia": evidencia,
        })
    return linhas


def _material_da_evidencia(evidencia: str | None) -> str | None:
    texto = evidencia or ""
    padroes = [
        r"\bASTM[- ]?[A-Z0-9. ]{2,24}",
        r"\bA[- ]?36\b",
        r"\bSAE[- ]?[0-9]{3,5}\b",
        r"\bCA[- ]?(?:25|50|60)\b",
        r"\bFCK\s*[0-9]+(?:[,.][0-9]+)?\s*MPA\b",
        r"\bSCH\s*[0-9A-Z/]+",
        r"\bM[0-9]{2,3}\b",
        r"\bDN\s*[0-9]{1,4}\b",
        r"\b(?:AÇO|ACO|CONCRETO|CHUMBADOR|TUBO|PERFIL|CHAPA)\b[^.;,\n]{0,50}",
    ]
    texto_norm = _norm_upper(texto)
    encontrados: list[str] = []
    for padrao in padroes:
        for match in re.finditer(padrao, texto_norm):
            valor = re.sub(r"\s+", " ", match.group(0)).strip(" -;,.")
            if valor and valor not in encontrados:
                encontrados.append(valor)
        if len(encontrados) >= 3:
            break
    return " / ".join(encontrados[:3]) if encontrados else None


def _descricao_quantitativo(item: ControleQuantitativo) -> str:
    evidencia = re.sub(r"\s+", " ", item.evidencia or "").strip()
    if evidencia:
        return evidencia[:180]
    return item.descricao or item.item or "Quantidade extraida do PDF"


def quantificar_controles_por_pdfs(db: Session, disciplina: str | None = None, limite: int | None = None) -> dict:
    controles = listar_controles(db)
    if disciplina:
        controles = [c for c in controles if _norm_upper(c.area) == _norm_upper(disciplina)]
    if limite:
        controles = controles[:limite]

    processados = 0
    com_pdf = 0
    com_quantidade = 0
    itens_criados = 0
    sem_pdf = []
    sem_texto_quantificavel = []
    pdfs = _pdfs_index()

    for controle in controles:
        processados += 1
        pdf = _localizar_pdf_documento(controle.documento_origem, pdfs=pdfs)
        db.query(ControleQuantitativo).filter(
            ControleQuantitativo.controle_id == controle.id,
            ControleQuantitativo.status_validacao == "Extraido automaticamente - revisar",
        ).delete(synchronize_session=False)
        if not pdf:
            sem_pdf.append(controle.documento_origem)
            db.commit()
            continue
        com_pdf += 1
        try:
            texto = _texto_pdf(pdf)
        except Exception:
            sem_texto_quantificavel.append(controle.documento_origem)
            db.commit()
            continue
        unidade = _unidade_principal(controle.controle_aplicavel)
        extraidos = _extrair_quantidades_texto(texto, unidade_preferida=unidade)
        if not extraidos:
            sem_texto_quantificavel.append(controle.documento_origem)
            db.commit()
            continue
        com_quantidade += 1
        for idx, item in enumerate(extraidos[:80], start=1):
            db.add(ControleQuantitativo(
                controle_id=controle.id,
                codigo_controle=controle.codigo_controle,
                documento_origem=controle.documento_origem,
                item=f"AUTO-{idx:03d}",
                descricao=f"Quantidade {item['unidade']} extraida automaticamente do PDF",
                unidade=item["unidade"],
                quantidade=item["quantidade"],
                fonte_arquivo=str(pdf),
                evidencia=item["evidencia"],
                status_validacao="Extraido automaticamente - revisar",
            ))
            itens_criados += 1
        db.commit()
    return {
        "processados": processados,
        "com_pdf": com_pdf,
        "com_quantidade": com_quantidade,
        "itens_criados": itens_criados,
        "sem_pdf": sem_pdf[:50],
        "sem_texto_quantificavel": sem_texto_quantificavel[:50],
    }


def listar_quantitativos_controles(db: Session) -> dict:
    """Retorna resumo por disciplina e uma planilha dos controles.

    Os quantitativos fisicos ainda dependem de extracao posterior dos PDFs.
    Nesta fase a planilha consolida o que ja existe de forma rastreavel:
    documento/controlador, tipo, unidade esperada, status e A4 equivalente.
    """
    lds = {doc.codigo_documento: doc for doc in db.query(LdDocumento).all()}
    sigems = {doc.codigo_documento: doc for doc in db.query(SigemDocumento).all()}
    itens_por_controle: dict[int, list[ControleQuantitativo]] = {}
    for item in db.query(ControleQuantitativo).all():
        itens_por_controle.setdefault(item.controle_id, []).append(item)
    linhas = []
    detalhes = []
    resumo: dict[str, dict] = {}

    controles = listar_controles(db)
    for controle in controles:
        ld = lds.get(controle.documento_origem)
        sigem = sigems.get(controle.documento_origem)
        if not sigem or not _eh_documentacao_tecnica_sigem(sigem):
            continue
        disciplina = controle.area or (ld.disciplina if ld else None) or (_area_sigem(sigem) if sigem else None) or "Geral"
        tipo = controle.controle_aplicavel or "Sem tipo"
        status = controle.status_controle or "Sem status"
        unidade = _unidade_principal(tipo)
        a4 = ld.a4_equivalente if ld else None
        itens = itens_por_controle.get(controle.id, [])
        itens_unidade = [item for item in itens if _normaliza_unidade(item.unidade) == unidade]
        quantidade_extraida = sum(item.quantidade for item in itens_unidade) if itens_unidade else None
        status_itens = {item.status_validacao for item in itens_unidade if item.status_validacao}
        evidencias = [item.evidencia for item in itens_unidade if item.evidencia]
        fontes = [item.fonte_arquivo for item in itens_unidade if item.fonte_arquivo]
        if itens_unidade:
            if len(status_itens) == 1:
                status_quant = next(iter(status_itens))
            elif status_itens:
                status_quant = "Validacao mista"
            else:
                status_quant = "Extraido automaticamente - revisar"
        elif itens:
            status_quant = "Extraido em outra unidade - revisar"
        else:
            status_quant = "Pendente extracao/validacao do documento"
        linha = {
            "controle_id": controle.id,
            "disciplina": disciplina,
            "tipo_controle": tipo,
            "codigo_controle": controle.codigo_controle,
            "documento": controle.documento_origem,
            "titulo": (ld.titulo if ld else None) or (_titulo_sigem(sigem) if sigem else None),
            "revisao": controle.revisao_documento,
            "status_controle": status,
            "unidade_principal": unidade,
            "quantidade_controle": 1,
            "quantidade_extraida": round(quantidade_extraida, 3) if quantidade_extraida is not None else None,
            "status_quantificacao": status_quant,
            "itens_extraidos": len(itens),
            "evidencia_quantificacao": evidencias[0] if evidencias else None,
            "fonte_arquivo": fontes[0] if fontes else None,
            "a4_equivalente": a4,
            "tem_pedido": bool(controle.tem_pedido),
            "tem_material": bool(controle.tem_material),
            "tem_montagem": bool(controle.tem_montagem),
            "entrou_medicao_report": bool(controle.entrou_medicao_report),
        }
        linhas.append(linha)

        for item in itens_unidade:
            detalhes.append({
                "quantitativo_id": item.id,
                "controle_id": controle.id,
                "disciplina": disciplina,
                "area": disciplina,
                "tipo_controle": tipo,
                "codigo_controle": controle.codigo_controle,
                "documento": controle.documento_origem,
                "desenho": controle.documento_origem,
                "titulo": (ld.titulo if ld else None) or (_titulo_sigem(sigem) if sigem else None),
                "revisao": controle.revisao_documento,
                "item": item.item,
                "descricao": _descricao_quantitativo(item),
                "material": _material_da_evidencia(item.evidencia),
                "unidade": _normaliza_unidade(item.unidade),
                "quantidade": round(item.quantidade, 3),
                "fonte_arquivo": item.fonte_arquivo,
                "evidencia": item.evidencia,
                "status_validacao": item.status_validacao or "Extraido automaticamente - revisar",
            })

        bucket = resumo.setdefault(disciplina, {
            "disciplina": disciplina,
            "controles": 0,
            "documentos": set(),
            "tipos": set(),
            "abertos": 0,
            "em_revisao": 0,
            "com_pedido": 0,
            "com_material": 0,
            "com_montagem": 0,
            "em_report": 0,
            "a4_total": 0.0,
            "extraido_m": 0.0,
            "extraido_kg": 0.0,
            "extraido_m3": 0.0,
            "extraido_un": 0.0,
            "controles_quantificados": set(),
        })
        bucket["controles"] += 1
        bucket["documentos"].add(controle.documento_origem)
        bucket["tipos"].add(tipo)
        status_norm = _norm_upper(status)
        if "ABERTO" in status_norm:
            bucket["abertos"] += 1
        if "REVIS" in status_norm:
            bucket["em_revisao"] += 1
        if controle.tem_pedido:
            bucket["com_pedido"] += 1
        if controle.tem_material:
            bucket["com_material"] += 1
        if controle.tem_montagem:
            bucket["com_montagem"] += 1
        if controle.entrou_medicao_report:
            bucket["em_report"] += 1
        if isinstance(a4, (int, float)):
            bucket["a4_total"] += float(a4)
        if quantidade_extraida is not None:
            bucket["controles_quantificados"].add(controle.codigo_controle)
            if unidade == "m":
                bucket["extraido_m"] += quantidade_extraida
            elif unidade == "kg":
                bucket["extraido_kg"] += quantidade_extraida
            elif unidade == "m3":
                bucket["extraido_m3"] += quantidade_extraida
            elif unidade == "un":
                bucket["extraido_un"] += quantidade_extraida

    resumo_lista = []
    for item in resumo.values():
        resumo_lista.append({
            **item,
            "documentos": len(item["documentos"]),
            "tipos": len(item["tipos"]),
            "controles_quantificados": len(item["controles_quantificados"]),
            "a4_total": round(item["a4_total"], 2),
            "extraido_m": round(item["extraido_m"], 3),
            "extraido_kg": round(item["extraido_kg"], 3),
            "extraido_m3": round(item["extraido_m3"], 3),
            "extraido_un": round(item["extraido_un"], 3),
        })

    resumo_lista.sort(key=lambda item: (-item["controles"], item["disciplina"]))
    linhas.sort(key=lambda item: (item["disciplina"], item["tipo_controle"], item["documento"], item["codigo_controle"]))
    detalhes.sort(key=lambda item: (item["disciplina"], item["tipo_controle"], item["documento"], item["item"] or ""))
    return {
        "resumo_disciplinas": resumo_lista,
        "planilha": linhas,
        "detalhes": detalhes,
    }


def validar_quantitativo_item(db: Session, item_id: int, status: str) -> dict:
    status_limpo = _norm(status) or "Validado"
    permitidos = {
        "Validado",
        "Revisar",
        "Rejeitado",
        "Extraido automaticamente - revisar",
    }
    if status_limpo not in permitidos:
        raise ValueError("Status de validacao invalido.")

    item = db.query(ControleQuantitativo).filter(ControleQuantitativo.id == item_id).first()
    if not item:
        raise ValueError("Quantitativo nao encontrado.")

    item.status_validacao = status_limpo
    item.atualizado_em = datetime.utcnow()
    db.commit()
    return {
        "quantitativo_id": item.id,
        "codigo_controle": item.codigo_controle,
        "status_validacao": status_limpo,
    }


def validar_quantitativos_controle(db: Session, codigo_controle: str, status: str) -> dict:
    status_limpo = _norm(status) or "Validado"
    permitidos = {
        "Validado",
        "Revisar",
        "Rejeitado",
        "Extraido automaticamente - revisar",
    }
    if status_limpo not in permitidos:
        raise ValueError("Status de validacao invalido.")

    itens = db.query(ControleQuantitativo).filter(
        ControleQuantitativo.codigo_controle == codigo_controle,
    ).all()
    if not itens:
        raise ValueError("Controle sem quantitativos extraidos.")

    agora = datetime.utcnow()
    for item in itens:
        item.status_validacao = status_limpo
        item.atualizado_em = agora
    db.commit()
    return {
        "codigo_controle": codigo_controle,
        "status_validacao": status_limpo,
        "itens_atualizados": len(itens),
    }
