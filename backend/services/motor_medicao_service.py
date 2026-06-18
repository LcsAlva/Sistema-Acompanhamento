"""Motor de Medição de Engenharia (Módulo 2 — Fase 2A).

Transforma o status SIGEM da LD em medição automática:

    SE status ∈ STATUS_APTOS  (default {"SEM WORKFLOW"})
    ENTÃO documento_medido = True, data_medicao = hoje, fator = 1.0 (100%)

Tudo PARAMETRIZADO via config/medicao.json (status aptos, buckets de
elaboração/análise, peso por A4 ou contagem) — nada fixo para a RECAP.

Expõe:
  - dashboard(db): totais globais (Totais, Em Elaboração, Em Análise,
    Sem Workflow, % Medido).
  - medicao_por_disciplina(db): docs/medidos/A4/% por disciplina.
  - evolucao_semanal(db): série semanal reconstruída de ld_historico_status.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from ..models import LdDocumento, LdHistoricoStatus, SigemDocumento, SigemHistoricoStatus

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "config", "medicao.json")

_DEFAULT_CONFIG = {
    "status_aptos": ["SEM WORKFLOW"],
    "status_em_elaboracao": ["EM ELABORACAO", "EM ELABORAÇÃO"],
    "status_em_analise": ["EM ANALISE", "EM ANÁLISE"],
    "peso_por": "a4_equivalente",
}


def normalizar_status(s: Optional[str]) -> str:
    """Uppercase, trim e colapsa espaços internos — robustez de matching."""
    if not s:
        return ""
    return " ".join(str(s).strip().upper().split())


def load_config() -> dict:
    try:
        with open(os.path.normpath(_CONFIG_PATH), encoding="utf-8") as fh:
            cfg = json.load(fh)
    except Exception:
        cfg = {}
    merged = {**_DEFAULT_CONFIG, **{k: v for k, v in cfg.items() if not k.startswith("_")}}
    # Normaliza os conjuntos de status para comparação consistente
    for chave in ("status_aptos", "status_em_elaboracao", "status_em_analise"):
        merged[chave] = {normalizar_status(x) for x in (merged.get(chave) or [])}
    return merged


def is_apto(status: Optional[str], cfg: Optional[dict] = None) -> bool:
    cfg = cfg or load_config()
    return normalizar_status(status) in cfg["status_aptos"]


def _peso(doc: LdDocumento, peso_por: str) -> float:
    if peso_por == "a4_equivalente":
        return float(doc.a4_equivalente or 0.0)
    return 1.0


def _peso_efetivo(docs: list[LdDocumento], peso_por: str) -> tuple[str, dict]:
    """Escolhe a métrica de peso; cai para contagem se nenhum A4 disponível."""
    if peso_por == "a4_equivalente" and not any((d.a4_equivalente or 0) > 0 for d in docs):
        return "contagem", {}
    return peso_por, {}


def _sigem_por_codigo(db: Session) -> dict[str, SigemDocumento]:
    return {s.codigo_documento: s for s in db.query(SigemDocumento).all()}


def resolver_status_oficial(doc: LdDocumento, sigem_por_codigo: dict[str, SigemDocumento]) -> tuple[Optional[str], str]:
    sigem = sigem_por_codigo.get(doc.codigo_documento)
    if sigem:
        return sigem.status, "SIGEM"
    return doc.status, "LD"


# ── Medição por disciplina ────────────────────────────────────────────────────
def medicao_por_disciplina(db: Session, cfg: Optional[dict] = None) -> list[dict]:
    cfg = cfg or load_config()
    docs = db.query(LdDocumento).all()
    sigem = _sigem_por_codigo(db)
    peso_por, _ = _peso_efetivo(docs, cfg["peso_por"])

    grupos: dict[str, dict] = {}
    for d in docs:
        disc = d.disciplina or "(sem disciplina)"
        g = grupos.setdefault(disc, {
            "disciplina": disc, "docs_totais": 0, "docs_medidos": 0,
            "peso_total": 0.0, "peso_medido": 0.0,
            "status_origem_sigem": 0, "status_origem_ld": 0,
        })
        peso = _peso(d, peso_por)
        status_oficial, origem_status = resolver_status_oficial(d, sigem)
        g["docs_totais"] += 1
        g["peso_total"] += peso
        if origem_status == "SIGEM":
            g["status_origem_sigem"] += 1
        else:
            g["status_origem_ld"] += 1
        if is_apto(status_oficial, cfg):
            g["docs_medidos"] += 1
            g["peso_medido"] += peso

    saida = []
    for g in grupos.values():
        base = g["peso_total"] if g["peso_total"] > 0 else g["docs_totais"]
        medido = g["peso_medido"] if g["peso_total"] > 0 else g["docs_medidos"]
        pct = (medido / base) if base > 0 else 0.0
        saida.append({
            **g,
            "peso_por": peso_por,
            "a4_acumulado": round(g["peso_medido"], 2) if peso_por == "a4_equivalente" else None,
            "a4_total": round(g["peso_total"], 2) if peso_por == "a4_equivalente" else None,
            "pct_medicao": round(pct, 6),
        })
    return sorted(saida, key=lambda x: x["disciplina"])


# ── Dashboard global ──────────────────────────────────────────────────────────
def dashboard(db: Session, cfg: Optional[dict] = None) -> dict:
    cfg = cfg or load_config()
    docs = db.query(LdDocumento).all()
    sigem = _sigem_por_codigo(db)
    peso_por, _ = _peso_efetivo(docs, cfg["peso_por"])

    total = len(docs)
    em_elab = em_anal = sem_wf = 0
    peso_total = peso_medido = 0.0
    origem_sigem = origem_ld = 0
    for d in docs:
        status_oficial, origem_status = resolver_status_oficial(d, sigem)
        if origem_status == "SIGEM":
            origem_sigem += 1
        else:
            origem_ld += 1
        st = normalizar_status(status_oficial)
        peso = _peso(d, peso_por)
        peso_total += peso
        if st in cfg["status_aptos"]:
            sem_wf += 1
            peso_medido += peso
        elif st in cfg["status_em_analise"]:
            em_anal += 1
        elif st in cfg["status_em_elaboracao"]:
            em_elab += 1

    base = peso_total if peso_total > 0 else total
    medido = peso_medido if peso_total > 0 else sem_wf
    pct = (medido / base) if base > 0 else 0.0
    return {
        "documentos_totais": total,
        "em_elaboracao": em_elab,
        "em_analise": em_anal,
        "sem_workflow": sem_wf,
        "outros": total - em_elab - em_anal - sem_wf,
        "pct_medido": round(pct, 6),
        "peso_por": peso_por,
        "status_origem_sigem": origem_sigem,
        "status_origem_ld": origem_ld,
        "a4_acumulado": round(peso_medido, 2) if peso_por == "a4_equivalente" else None,
        "a4_total": round(peso_total, 2) if peso_por == "a4_equivalente" else None,
    }


# ── Evolução semanal (reconstruída do histórico) ──────────────────────────────
def _status_em(doc_historico: list[LdHistoricoStatus], status_atual: str,
               ref: datetime) -> str:
    """Status que o documento tinha NA data `ref`, dado o histórico de transições.

    Pega a última transição com data_alteracao <= ref; se nenhuma, considera que
    ainda não existia/estava no status mais antigo conhecido.
    """
    relevantes = [h for h in doc_historico if h.data_alteracao and h.data_alteracao <= ref]
    if relevantes:
        return relevantes[-1].status_novo
    # antes da 1ª transição: usa o status_anterior da primeira, se houver
    if doc_historico:
        return doc_historico[0].status_anterior or ""
    return status_atual


def evolucao_semanal(db: Session, semanas: int = 12, cfg: Optional[dict] = None) -> list[dict]:
    """Série semanal de quantos documentos estavam aptos (SEM WORKFLOW) ao fim
    de cada semana, reconstruída de ld_historico_status (sem tabela extra)."""
    cfg = cfg or load_config()
    docs = db.query(LdDocumento).all()
    sigem = _sigem_por_codigo(db)
    if not docs:
        return []

    historicos: dict[int, list[LdHistoricoStatus]] = {}
    for h in (db.query(LdHistoricoStatus)
              .order_by(LdHistoricoStatus.data_alteracao).all()):
        historicos.setdefault(h.documento_id, []).append(h)

    sigem_historicos: dict[int, list[SigemHistoricoStatus]] = {}
    for h in (db.query(SigemHistoricoStatus)
              .order_by(SigemHistoricoStatus.data_alteracao).all()):
        sigem_historicos.setdefault(h.documento_id, []).append(h)

    hoje = date.today()
    # Domingo (fim) de cada semana, das mais antigas para a atual
    fim_semana_atual = hoje + timedelta(days=(6 - hoje.weekday()))
    pontos = []
    for i in range(semanas - 1, -1, -1):
        fim = fim_semana_atual - timedelta(weeks=i)
        ref = datetime.combine(fim, datetime.max.time())
        aptos = 0
        for d in docs:
            sigem_doc = sigem.get(d.codigo_documento)
            if sigem_doc:
                st = _status_em(sigem_historicos.get(sigem_doc.id, []), sigem_doc.status or "", ref)
            else:
                st = _status_em(historicos.get(d.id, []), d.status or "", ref)
            if normalizar_status(st) in cfg["status_aptos"]:
                aptos += 1
        pontos.append({
            "semana_fim": fim.isoformat(),
            "sem_workflow": aptos,
            "documentos_totais": len(docs),
            "pct_medido": round(aptos / len(docs), 6) if docs else 0.0,
        })
    return pontos
