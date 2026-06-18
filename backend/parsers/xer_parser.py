"""
Parser XER para o Sistema de Programação Semanal URFCC.

O formato XER do Oracle Primavera P6 é texto tabulado:
  %T  TASK
  %F  task_id\twbs_id\tproj_id\t...
  %R  12345\t67890\t11111\t...
  %T  PROJWBS
  ...
  %E  (fim do arquivo)

Tabelas utilizadas:
  TASK      — dados da atividade (datas, %, equip qty)
  PROJWBS   — hierarquia WBS (área/unidade, código WBS)
  TASKACTV  — associação atividade ↔ código P6
  ACTVCODE  — valores dos códigos (ex: "Construção Civil")
  ACTVTYPE  — tipos de código (ex: "URFCC-Fase")

Mapeamento de campos (XER → sistema):
  task_code              → activity_id
  task_name              → nome
  status_code            → status_atividade
  target_drtn_hr_cnt     → duracao (horas → dias /8h)
  early_start_date       → inicio_prog   (data programada atual — Early Start)
  early_end_date         → termino_prog  (data programada atual — Early Finish)
  target_start_date      → inicio_lb     (linha de base)
  target_end_date        → termino_lb    (linha de base)
  phys_complete_pct      → pct_avanco    (equivalente a sched_complete_pct)
  act_equip_qty /        → pct_executado (equivalente a equip_complete_pct)
    target_equip_qty
  target_equip_qty       → unid_orcadas_smo  ← CRÍTICO para filtro QCRON
  TASKACTV tipo 216      → disciplina    (URFCC-Fase)
  PROJWBS.wbs_name       → area_unidade  (nó WBS mais próximo)
  caminho WBS montado    → wbs_codigo    (ex: URFCC-2026-04-1.3.1.2)

Nota sobre datas:
  - early_start/end = datas calculadas pelo scheduler (forward pass)
    → são as datas "programadas" para tarefas não iniciadas (TK_NotStart) e ativas (TK_Active)
  - Para tarefas concluídas (TK_Complete), o P6 pode congelar early em 23:59 do
    período anterior; usamos act_start/end_date quando early estiver zerado ou implausível.
"""

import json
import re
from datetime import date, datetime
from typing import Optional


# ── Constantes ──────────────────────────────────────────────────────────────

# actv_code_type_id do XER deste projeto que mapeia para "Disciplina"
_FASE_TYPE_ID = "216"     # URFCC-Fase  (Construção Civil, Caldeiraria, …)
_EAP_TYPE_ID  = "222"     # URFCC-EAP   (fallback quando Fase não está definido)

# Mapeamento do dígito de disciplina no código WBS → nome
# Idêntico ao xlsx_parser.DISCIPLINA_MAP para garantir strings iguais nos dois parsers
_WBS_RE = re.compile(r'URFCC-\d{4}-\d{2}-\d+\.(\d)')
_DISCIPLINA_MAP = {
    "0": "Marcos",
    "1": "Mobilização",
    "2": "Engenharia de detalhamento",
    "3": "Construção Civil",
    "4": "Eletromecânica",
    "5": "Comissionamento",
    "6": "Fornecimento de bens",
}


# ── Ponto de entrada ─────────────────────────────────────────────────────────

def parse_xer(conteudo: str) -> list[dict]:
    """
    Parseia um arquivo XER e retorna lista de dicts de tarefas.
    Equivalente ao parse_xlsx para fins de _persistir_tarefas.
    """
    tabelas = _extrair_tabelas(conteudo)

    tasks     = tabelas.get("TASK", [])
    wbs_map   = _build_wbs_map(tabelas.get("PROJWBS", []))
    code_map  = {r["actv_code_id"]: r for r in tabelas.get("ACTVCODE", [])}
    task_actv = tabelas.get("TASKACTV", [])

    # task_id → {type_id: nome_do_código}
    actv_por_task: dict[str, dict[str, str]] = {}
    for r in task_actv:
        tid = r.get("task_id", "")
        tipo = r.get("actv_code_type_id", "")
        nome = code_map.get(r.get("actv_code_id", ""), {}).get("actv_code_name", "")
        if tid:
            actv_por_task.setdefault(tid, {})[tipo] = nome

    tarefas = []
    for row in tasks:
        tarefa = _processar_task(row, wbs_map, actv_por_task)
        if tarefa and tarefa.get("activity_id"):
            tarefas.append(tarefa)

    return tarefas


# ── Processamento de uma tarefa ───────────────────────────────────────────────

def _processar_task(
    row: dict,
    wbs_map: dict[str, dict],
    actv_por_task: dict[str, dict[str, str]],
) -> Optional[dict]:
    """Converte uma linha da tabela TASK em dict para _persistir_tarefas."""

    activity_id = (row.get("task_code") or "").strip()
    if not activity_id:
        return None

    # ── Datas programadas (Early Start / Early Finish) ────────────────────
    # Para TK_Complete, early fica congelado. Usa act quando early estiver
    # na data de congelamento ou vazio.
    early_start = _xer_date(row.get("early_start_date"))
    early_end   = _xer_date(row.get("early_end_date"))
    act_start   = _xer_date(row.get("act_start_date"))
    act_end     = _xer_date(row.get("act_end_date"))

    status_code = (row.get("status_code") or "").strip()
    is_complete = status_code == "TK_Complete"

    # Para concluídas: usa datas reais; para demais: usa early
    if is_complete and act_start and act_end:
        inicio_prog  = act_start
        termino_prog = act_end
    else:
        inicio_prog  = early_start
        termino_prog = early_end

    # ── Linha de base ─────────────────────────────────────────────────────
    inicio_lb  = _xer_date(row.get("target_start_date"))
    termino_lb = _xer_date(row.get("target_end_date"))

    # ── % de avanço previsto (sched_complete_pct equivalente) ─────────────
    pct_avanco = _float_or_none(row.get("phys_complete_pct")) or 0.0

    # ── % executado (equip_complete_pct = act_equip / target_equip * 100) ─
    target_equip = _float_or_none(row.get("target_equip_qty")) or 0.0
    act_equip    = _float_or_none(row.get("act_equip_qty"))    or 0.0
    if target_equip > 0:
        pct_executado    = round(act_equip / target_equip * 100, 2)
        unid_orcadas_smo = target_equip
    else:
        pct_executado    = None   # sinaliza "coluna ausente" para o filtro QCRON
        unid_orcadas_smo = None   # None = ignora filtro SMO (XER sem recurso equipamento → não exclui do QCRON)

    # ── Duração (horas → dias, 8 h/dia) ──────────────────────────────────
    dur_horas = _float_or_none(row.get("target_drtn_hr_cnt"))
    duracao = round(dur_horas / 8) if dur_horas else None

    # ── WBS → área/unidade, código WBS e caminho hierárquico ─────────────
    wbs_id       = row.get("wbs_id", "")
    area_unidade = wbs_map.get(wbs_id, {}).get("wbs_name")
    wbs_codigo   = _build_wbs_codigo(wbs_id, wbs_map)
    wbs_path_list = _build_wbs_path(wbs_id, wbs_map)
    wbs_path_json = json.dumps(wbs_path_list, ensure_ascii=False) if wbs_path_list else None

    # ── Disciplina: prioridade WBS (igual ao xlsx_parser) ────────────────
    # O Excel deriva disciplina SEMPRE pelo caminho WBS — o código de atividade
    # URFCC-Fase pode divergir (ex: tasks URFCC-S sob WBS .6 = Fornecimento de
    # bens mas com Fase = "Montagem Eletromecânica"). WBS é a fonte autoritativa.
    task_id  = row.get("task_id", "")
    atos     = actv_por_task.get(task_id, {})
    disciplina = None
    if wbs_codigo:
        m = _WBS_RE.search(wbs_codigo)
        if m:
            disciplina = _DISCIPLINA_MAP.get(m.group(1))
    # Fallback: usa URFCC-Fase apenas se WBS não der disciplina
    if not disciplina:
        disciplina = atos.get(_FASE_TYPE_ID) or atos.get(_EAP_TYPE_ID) or None

    return {
        "activity_id":      activity_id,
        "nome":             (row.get("task_name") or "").strip() or activity_id,
        "status_atividade": _mapear_status(status_code),
        "disciplina":       disciplina,
        "area_unidade":     area_unidade,
        "wbs_codigo":       wbs_codigo,
        "wbs_path":         wbs_path_json,
        "duracao":          duracao,
        "inicio_prog":      inicio_prog,
        "termino_prog":     termino_prog,
        "inicio_lb":        inicio_lb,
        "termino_lb":       termino_lb,
        "pct_avanco":       pct_avanco,
        "pct_executado":    pct_executado,
        "unid_orcadas_smo": unid_orcadas_smo,
        # supervisor/encarregado não disponíveis no XER padrão
        "supervisor":       None,
        "encarregado":      None,
    }


# ── Helpers ──────────────────────────────────────────────────────────────────

def _extrair_tabelas(conteudo: str) -> dict[str, list[dict]]:
    """Lê o XER linha a linha e agrupa em tabelas dict."""
    tabelas: dict[str, list[dict]] = {}
    tabela_atual = None
    campos_atuais: list[str] = []

    for linha in conteudo.splitlines():
        linha = linha.rstrip("\r")
        if not linha:
            continue

        if linha.startswith("%T"):
            tabela_atual = linha[2:].strip()
            campos_atuais = []
            tabelas[tabela_atual] = []

        elif linha.startswith("%F"):
            campos_atuais = linha[2:].strip().split("\t")

        elif linha.startswith("%R"):
            if tabela_atual and campos_atuais:
                valores = linha[2:].strip().split("\t")
                row = dict(zip(campos_atuais, valores))
                tabelas[tabela_atual].append(row)

        elif linha.startswith("%E"):
            break

    return tabelas


def _build_wbs_map(wbs_rows: list[dict]) -> dict[str, dict]:
    """Cria mapa wbs_id → dados do nó WBS."""
    return {row["wbs_id"]: row for row in wbs_rows if "wbs_id" in row}


def _build_wbs_codigo(wbs_id: str, wbs_map: dict[str, dict]) -> Optional[str]:
    """
    Reconstrói o código WBS com caminho completo percorrendo a hierarquia.
    Exemplo: URFCC-2026-04-1.3.1.2.4

    O nó raiz tem short_name no formato 'URFCC-YYYY-MM-N'.
    Os filhos têm short_name numérico (1, 2, 3, …).
    """
    if not wbs_id or wbs_id not in wbs_map:
        return None

    partes: list[str] = []
    cur = wbs_id
    while cur and cur in wbs_map:
        node = wbs_map[cur]
        short = (node.get("wbs_short_name") or "").strip()
        if short:
            partes.append(short)
        parent = node.get("parent_wbs_id", "")
        if not parent or parent not in wbs_map:
            break
        cur = parent

    if not partes:
        return None

    partes.reverse()
    # primeiro elemento é o código raiz (ex: URFCC-2026-04-1),
    # demais são números separados por ponto
    if len(partes) == 1:
        return partes[0]
    return partes[0] + "." + ".".join(partes[1:])


def _build_wbs_path(wbs_id: str, wbs_map: dict[str, dict]) -> list[str]:
    """
    Retorna lista de wbs_name do nó raiz até o nó dado (inclusive).
    Ex: ["RECAP REVAMP URFCC...", "MONTAGEM ELETROMECÂNICA", "Tubulação", "Pintura"]
    """
    if not wbs_id or wbs_id not in wbs_map:
        return []

    names: list[str] = []
    cur = wbs_id
    while cur and cur in wbs_map:
        node = wbs_map[cur]
        name = (node.get("wbs_name") or "").strip()
        if name:
            names.append(name)
        parent = node.get("parent_wbs_id", "")
        if not parent or parent not in wbs_map:
            break
        cur = parent

    names.reverse()
    return names


def _mapear_status(status_code: str) -> Optional[str]:
    """Converte status_code P6 para string legível (igual ao XLSX)."""
    mapa = {
        "TK_Complete": "Concluído",
        "TK_Active":   "Em Progresso",
        "TK_NotStart": "Não Iniciado",
    }
    return mapa.get(status_code, status_code or None)


def _xer_date(valor: Optional[str]) -> Optional[date]:
    """Converte string de data XER ('YYYY-MM-DD HH:MM') para objeto date."""
    if not valor or not valor.strip():
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(valor.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _float_or_none(valor: Optional[str]) -> Optional[float]:
    """
    Converte string para float; retorna None se inválido ou vazio.
    Suporta separador decimal vírgula (ex: exportações BRL do P6: "51,76").
    """
    if valor is None or valor == "":
        return None
    try:
        return float(valor)
    except (ValueError, TypeError):
        pass
    # Tenta normalizar separador decimal vírgula → ponto (formato BRL)
    try:
        return float(valor.replace(",", "."))
    except (ValueError, TypeError):
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# MÓDULO PRODUÇÃO — extração orientada ao cronograma real (independente do import
# da Programação Semanal acima). Disciplina vem do código de atividade real
# "URFCC-Disciplina" (25 valores); peso = duração da atividade (ponderação).
# ═══════════════════════════════════════════════════════════════════════════════

_STATUS_PROD = {
    "TK_Complete": "concluida",
    "TK_Active": "em_andamento",
    "TK_NotStart": "nao_iniciada",
}


def extrair_producao(conteudo: str) -> dict:
    """Extrai projeto, WBS e atividades do XER para o módulo Produção.

    Sem inventar dados: campos ausentes voltam como None/0.
    """
    tabelas = _extrair_tabelas(conteudo)
    rows = lambda t: tabelas.get(t, [])

    # ── Projeto / data date ──────────────────────────────────────────────
    proj = (rows("PROJECT") or [{}])[0]
    data_date = _xer_date(proj.get("last_recalc_date")) or _xer_date(proj.get("apply_actuals_date"))
    projeto = {
        "proj_short_name": proj.get("proj_short_name") or "",
        "data_date": data_date,
        "plan_start": _xer_date(proj.get("plan_start_date")),
        "plan_end": _xer_date(proj.get("scd_end_date")) or _xer_date(proj.get("plan_end_date")),
    }

    # ── Tipos de código de atividade (Disciplina / Fase / Agrupamento) ────
    tipo_por_id = {r.get("actv_code_type_id"): (r.get("actv_code_type") or "") for r in rows("ACTVTYPE")}

    def _tipo_id(substr: str) -> Optional[str]:
        for tid, nome in tipo_por_id.items():
            if substr.lower() in (nome or "").lower():
                return tid
        return None

    id_disc, id_fase, id_agrup = _tipo_id("disciplina"), _tipo_id("fase"), _tipo_id("agrupamento")

    code_info = {r.get("actv_code_id"): (r.get("actv_code_type_id"), r.get("actv_code_name") or "")
                 for r in rows("ACTVCODE")}

    task_codes: dict[str, dict] = {}
    for r in rows("TASKACTV"):
        info = code_info.get(r.get("actv_code_id"))
        if not info:
            continue
        type_id, nome = info
        d = task_codes.setdefault(r.get("task_id"), {})
        if type_id == id_disc:
            d["disciplina"] = nome
        elif type_id == id_fase:
            d["fase"] = nome
        elif type_id == id_agrup:
            d["area"] = nome

    # ── UDF responsável (Supervisor/Encarregado/Coordenador) ─────────────
    udf_label = {r.get("udf_type_id"): (r.get("udf_type_label") or "") for r in rows("UDFTYPE")}
    ids_resp, ranks = [], {}
    for label in ("Supervisor1", "Encarregado1", "Coordenador1"):
        for uid, lbl in udf_label.items():
            if (lbl or "").lower() == label.lower():
                ranks[uid] = len(ids_resp); ids_resp.append(uid)
    resp_por_task, best = {}, {}
    if ids_resp:
        for r in rows("UDFVALUE"):
            uid = r.get("udf_type_id")
            if uid not in ranks:
                continue
            tid, txt = r.get("fk_id"), (r.get("udf_text") or "").strip()
            if txt and (tid not in best or ranks[uid] < best[tid]):
                best[tid] = ranks[uid]; resp_por_task[tid] = txt

    # ── WBS ──────────────────────────────────────────────────────────────
    wbs_por_id = {r.get("wbs_id"): {
        "wbs_id": r.get("wbs_id"), "parent_wbs_id": r.get("parent_wbs_id"),
        "short_name": r.get("wbs_short_name") or "", "nome": r.get("wbs_name") or "",
        "is_node": r.get("proj_node_flag") == "Y",
    } for r in rows("PROJWBS")}

    # ── Ponderação física: recurso "PONDERADOR" (detectado por nome) ─────
    # Peso oficial da obra = unidades físicas (target_qty) do recurso ponderador.
    # Realizado = act_reg_qty. NÃO usar duração nem phys_complete_pct.
    # Detecção por nome (reutilizável entre contratos), não pelo id fixo.
    rsrc_pond = {r.get("rsrc_id") for r in rows("RSRC")
                 if "PONDERADOR" in ((r.get("rsrc_name") or r.get("rsrc_short_name") or "").upper())}
    pond_target: dict[str, float] = {}
    pond_real: dict[str, float] = {}
    pond_remain: dict[str, float] = {}
    for r in rows("TASKRSRC"):
        if r.get("rsrc_id") in rsrc_pond:
            tid = r.get("task_id")
            pond_target[tid] = pond_target.get(tid, 0.0) + (_float_or_none(r.get("target_qty")) or 0.0)
            pond_real[tid] = pond_real.get(tid, 0.0) + (_float_or_none(r.get("act_reg_qty")) or 0.0) \
                + (_float_or_none(r.get("act_ot_qty")) or 0.0)
            pond_remain[tid] = pond_remain.get(tid, 0.0) + (_float_or_none(r.get("remain_qty")) or 0.0)

    # ── Atividades ───────────────────────────────────────────────────────
    atividades = []
    for r in rows("TASK"):
        tid = r.get("task_id")
        codes = task_codes.get(tid, {})
        ts, te = _xer_date(r.get("target_start_date")), _xer_date(r.get("target_end_date"))
        as_, ae = _xer_date(r.get("act_start_date")), _xer_date(r.get("act_end_date"))
        status_code = r.get("status_code")
        # Peso físico oficial = unidades do PONDERADOR (target_qty). Sem duração.
        peso = pond_target.get(tid, 0.0)
        unid_realizada = pond_real.get(tid, 0.0)
        unid_remaining = pond_remain.get(tid, 0.0)
        tf = r.get("total_float_hr_cnt")
        tf_val = _float_or_none(tf) if tf not in (None, "") else None
        concluida = status_code == "TK_Complete"
        atividades.append({
            "task_code": r.get("task_code") or "",
            "nome": r.get("task_name") or "",
            "wbs_id": r.get("wbs_id"),
            "wbs_nome": wbs_por_id.get(r.get("wbs_id"), {}).get("nome", ""),
            "disciplina": codes.get("disciplina"),
            "fase": codes.get("fase"),
            "area": codes.get("area"),
            "status": _STATUS_PROD.get(status_code, "nao_iniciada"),
            "phys_pct": _float_or_none(r.get("phys_complete_pct")) or 0.0,   # referência (não usado no avanço)
            "peso": peso,                       # unidades orçadas do PONDERADOR (peso físico)
            "unid_realizada": unid_realizada,   # unidades realizadas (act_reg_qty + act_ot_qty)
            "unid_remaining": unid_remaining,   # unidades restantes (remain_qty) → tendência
            "target_start": ts, "target_end": te,
            "act_start": as_, "act_end": ae,
            "total_float_hr": tf_val,
            "critica": (not concluida) and (tf_val is not None) and (tf_val <= 0),
            "is_marco": r.get("task_type") in ("TT_Mile", "TT_FinMile"),
            "responsavel": resp_por_task.get(tid),
        })

    return {
        "projeto": projeto,
        "wbs": list(wbs_por_id.values()),
        "atividades": atividades,
        "disciplinas_detectadas": sorted({a["disciplina"] for a in atividades if a["disciplina"]}),
        "ponderador_encontrado": bool(rsrc_pond),
        "peso_total": round(sum(pond_target.values()), 2),
        "unid_realizada_total": round(sum(pond_real.values()), 2),
    }
