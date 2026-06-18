"""Matriz de Critérios de Medição Petrobras (Módulo 3 — Fase 2A).

Espinha da PARAMETRIZAÇÃO do sistema de medição. Cada item da EAP possui um
critério (`criterios_medicao`), e cada `tipo_criterio` é resolvido por um
HANDLER registrado num registry de estratégias. Assim, nenhuma regra é fixa
para a RECAP: trocar o contrato = trocar os critérios/parametros, sem mexer
no código.

Handlers implementados na Fase 2A:
  - DOCUMENTO_SEM_WORKFLOW: % a partir da LD/SIGEM (Módulo 2). Consome
    `motor_medicao_service.medicao_por_disciplina`.
  - MANUAL: medição lançada manualmente (sem cálculo automático).

Handlers registrados mas PENDENTES de fonte (Fase 2C): PESO_TUBULACAO, ESTACA,
BASE_CONCRETO, FABRICACAO_ESTRUTURA, MONTAGEM_ESTRUTURA — retornam pct=0 com
`fonte_pendente=True`, prontos para receber suas fontes (Produção, CAE 3D,
Controle Fabricação).
"""
from __future__ import annotations

import json
from typing import Callable, Optional

from sqlalchemy.orm import Session

from ..models import CriterioMedicao, EapItem


# ── Catálogo de tipos de critério (parametrizável) ────────────────────────────
# Cada entrada: (descrição amigável, implementado?)
TIPOS_CRITERIO: dict[str, dict] = {
    "MANUAL":                 {"descricao": "Medição manual (sem cálculo automático)", "implementado": True},
    "DOCUMENTO_SEM_WORKFLOW": {"descricao": "Engenharia: documento SEM WORKFLOW = 100% (LD/SIGEM)", "implementado": True},
    "PESO_TUBULACAO":         {"descricao": "Tubulação por peso (kg) — fonte Produção", "implementado": False},
    "ESTACA":                 {"descricao": "Estacas executadas — fonte Produção", "implementado": False},
    "BASE_CONCRETO":          {"descricao": "Bases de concreto (m³) — fonte Produção", "implementado": False},
    "FABRICACAO_ESTRUTURA":   {"descricao": "Fabricação de estrutura metálica — Controle Fabricação", "implementado": False},
    "MONTAGEM_ESTRUTURA":     {"descricao": "Montagem de estrutura metálica — fonte Produção", "implementado": False},
}

TIPO_DEFAULT = "MANUAL"


# ── Resultado padrão de um handler ────────────────────────────────────────────
def _resultado(pct: Optional[float], *, implementado: bool, fonte_pendente: bool = False,
               manual: bool = False, evidencias: Optional[list] = None,
               detalhe: str = "") -> dict:
    return {
        "pct": pct,                       # 0..1 ou None (manual/pendente)
        "implementado": implementado,
        "fonte_pendente": fonte_pendente,
        "manual": manual,
        "evidencias": evidencias or [],
        "detalhe": detalhe,
    }


def _parse_parametros(criterio: CriterioMedicao) -> dict:
    if not criterio or not criterio.parametros:
        return {}
    try:
        return json.loads(criterio.parametros) or {}
    except (ValueError, TypeError):
        return {}


# ── Handlers (estratégias) ────────────────────────────────────────────────────
def _handler_manual(eap_item, criterio, db, contexto) -> dict:
    return _resultado(None, implementado=True, manual=True,
                      detalhe="Medição lançada manualmente.")


def _handler_documento_sem_workflow(eap_item, criterio, db, contexto) -> dict:
    """% de engenharia a partir da LD/SIGEM.

    `parametros.disciplina` filtra a disciplina-alvo na LD. Sem disciplina,
    usa a medição global de engenharia.
    """
    from . import motor_medicao_service as motor  # import tardio evita ciclo

    params = _parse_parametros(criterio)
    disciplina = params.get("disciplina")
    medicoes = motor.medicao_por_disciplina(db)

    if disciplina:
        alvo = next((m for m in medicoes if (m["disciplina"] or "").upper() == disciplina.upper()), None)
        if not alvo:
            return _resultado(0.0, implementado=True,
                              detalhe=f"Sem documentos na LD para disciplina '{disciplina}'.")
        return _resultado(alvo["pct_medicao"], implementado=True,
                          evidencias=[f"{alvo['docs_medidos']}/{alvo['docs_totais']} docs SEM WORKFLOW"],
                          detalhe=f"Disciplina {disciplina}: {alvo['pct_medicao'] * 100:.1f}%")

    glob = motor.dashboard(db)
    return _resultado(glob["pct_medido"], implementado=True,
                      evidencias=[f"{glob['sem_workflow']}/{glob['documentos_totais']} docs SEM WORKFLOW"],
                      detalhe=f"Engenharia global: {glob['pct_medido'] * 100:.1f}%")


def _handler_pendente(eap_item, criterio, db, contexto) -> dict:
    tipo = criterio.tipo_criterio if criterio else "?"
    return _resultado(0.0, implementado=False, fonte_pendente=True,
                      detalhe=f"Tipo '{tipo}' aguarda integração de fonte externa (Fase 2C).")


# Registry: tipo_criterio → handler. Tipos do catálogo sem handler real usam
# _handler_pendente. Trocar/estender = registrar nova função aqui.
CRITERIO_HANDLERS: dict[str, Callable] = {
    "MANUAL": _handler_manual,
    "DOCUMENTO_SEM_WORKFLOW": _handler_documento_sem_workflow,
}


def resolver_handler(tipo_criterio: str) -> Callable:
    return CRITERIO_HANDLERS.get(tipo_criterio, _handler_pendente)


# ── API de domínio ────────────────────────────────────────────────────────────
def get_criterio(db: Session, codigo_eap: str) -> Optional[CriterioMedicao]:
    return db.query(CriterioMedicao).filter(CriterioMedicao.codigo_eap == codigo_eap).first()


def listar_criterios(db: Session, tipo: Optional[str] = None,
                     ativo: Optional[bool] = None) -> list[CriterioMedicao]:
    q = db.query(CriterioMedicao)
    if tipo:
        q = q.filter(CriterioMedicao.tipo_criterio == tipo)
    if ativo is not None:
        q = q.filter(CriterioMedicao.ativo == ativo)
    return q.order_by(CriterioMedicao.codigo_eap).all()


def upsert_criterio(db: Session, payload: dict) -> CriterioMedicao:
    """Cria ou atualiza o critério de um item EAP (chave: codigo_eap)."""
    codigo = payload["codigo_eap"]
    crit = get_criterio(db, codigo)
    params = payload.get("parametros")
    if isinstance(params, (dict, list)):
        params = json.dumps(params, ensure_ascii=False)
    campos = dict(
        descricao=payload.get("descricao"),
        tipo_criterio=payload.get("tipo_criterio") or TIPO_DEFAULT,
        peso=payload.get("peso", 1.0),
        evidencia_obrigatoria=payload.get("evidencia_obrigatoria", False),
        ativo=payload.get("ativo", True),
        parametros=params,
    )
    if crit:
        for k, v in campos.items():
            if v is not None or k in ("parametros", "descricao"):
                setattr(crit, k, v)
    else:
        crit = CriterioMedicao(codigo_eap=codigo, **campos)
        db.add(crit)
    db.commit()
    db.refresh(crit)
    return crit


def deletar_criterio(db: Session, codigo_eap: str) -> bool:
    crit = get_criterio(db, codigo_eap)
    if not crit:
        return False
    db.delete(crit)
    db.commit()
    return True


def seed_from_eap(db: Session, tipo_default: str = TIPO_DEFAULT) -> dict:
    """Cria um critério default para cada item EAP que ainda não tem um.

    Não sobrescreve critérios existentes. Idempotente.
    """
    existentes = {c.codigo_eap for c in db.query(CriterioMedicao.codigo_eap).all()}
    criados = 0
    for item in db.query(EapItem).all():
        if item.codigo in existentes:
            continue
        db.add(CriterioMedicao(
            codigo_eap=item.codigo,
            descricao=item.descricao,
            tipo_criterio=tipo_default,
            peso=1.0,
            evidencia_obrigatoria=False,
            ativo=True,
        ))
        criados += 1
    db.commit()
    return {"criados": criados, "ja_existentes": len(existentes)}


def avaliar_criterio(db: Session, codigo_eap: str, contexto: Optional[dict] = None) -> dict:
    """Resolve o handler do critério de um item EAP e devolve o resultado.

    Retorna sempre um dict no formato de `_resultado`, acrescido de
    `codigo_eap`/`tipo_criterio`. Item sem critério é tratado como MANUAL.
    """
    crit = get_criterio(db, codigo_eap)
    eap_item = db.query(EapItem).filter(EapItem.codigo == codigo_eap).first()
    tipo = crit.tipo_criterio if crit else TIPO_DEFAULT
    handler = resolver_handler(tipo)
    res = handler(eap_item, crit, db, contexto or {})
    res["codigo_eap"] = codigo_eap
    res["tipo_criterio"] = tipo
    return res
