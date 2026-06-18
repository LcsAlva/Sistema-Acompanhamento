"""Serviço do módulo Produção — painel executivo do cronograma (XER).

Ponderação por DURAÇÃO (peso = horas de duração da atividade).
Planejado: fração da duração decorrida entre target_start→target_end.
Realizado: peso × phys_complete_pct, distribuído pelas datas reais.
"tudo baseado na estrutura real do XER" — nada fictício; o que falta é sinalizado.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from ..models import ProdProjeto, ProdWbs, ProdAtividade


# ── Importação ───────────────────────────────────────────────────────────────
def importar_xer(db: Session, parsed: dict, filename: str) -> dict:
    """Substitui o projeto ativo pelo cronograma do XER parseado."""
    for p in db.query(ProdProjeto).filter(ProdProjeto.ativo.is_(True)).all():
        p.ativo = False
    db.flush()

    pj = parsed["projeto"]
    projeto = ProdProjeto(
        proj_short_name=pj["proj_short_name"], data_date=pj["data_date"],
        plan_start=pj["plan_start"], plan_end=pj["plan_end"],
        origem_arquivo=filename, total_atividades=len(parsed["atividades"]), ativo=True,
    )
    db.add(projeto)
    db.flush()

    for w in parsed["wbs"]:
        db.add(ProdWbs(projeto_id=projeto.id, wbs_uid=w["wbs_id"], parent_uid=w["parent_wbs_id"],
                       short_name=w["short_name"], nome=w["nome"], is_node=w["is_node"]))
    for a in parsed["atividades"]:
        db.add(ProdAtividade(
            projeto_id=projeto.id, task_code=a["task_code"], nome=a["nome"],
            wbs_uid=a["wbs_id"], wbs_nome=a["wbs_nome"], disciplina=a["disciplina"],
            fase=a["fase"], area=a["area"], status=a["status"], phys_pct=a["phys_pct"],
            peso=a["peso"], unid_realizada=a.get("unid_realizada", 0.0),
            unid_remaining=a.get("unid_remaining", 0.0),
            target_start=a["target_start"], target_end=a["target_end"],
            act_start=a["act_start"], act_end=a["act_end"], total_float_hr=a["total_float_hr"],
            critica=a["critica"], is_marco=a["is_marco"], responsavel=a["responsavel"],
        ))
    db.commit()
    db.refresh(projeto)
    return {
        "projeto_id": projeto.id, "proj_short_name": projeto.proj_short_name,
        "data_date": projeto.data_date.isoformat() if projeto.data_date else None,
        "total_atividades": projeto.total_atividades,
        "disciplinas": parsed["disciplinas_detectadas"],
    }


def get_projeto_ativo(db: Session) -> Optional[ProdProjeto]:
    return (db.query(ProdProjeto).filter(ProdProjeto.ativo.is_(True))
            .order_by(ProdProjeto.importado_em.desc()).first())


# ── Matemática da curva (ponderação por duração) ─────────────────────────────
def _planned_frac(a: ProdAtividade, d: date) -> float:
    ts, te = a.target_start, a.target_end
    if not ts or not te or te <= ts:
        ref = te or ts
        return 1.0 if (ref and d >= ref) else 0.0
    if d <= ts:
        return 0.0
    if d >= te:
        return 1.0
    return (d - ts).days / (te - ts).days


def _realized_time_frac(a: ProdAtividade, d: date, data_date: date) -> float:
    """Fração das unidades realizadas já incorridas até a data d.

    Distribui as unidades realizadas (act_reg_qty) pelas datas reais, para
    montar a curva realizada ao longo do tempo. Em d = data date → 1 (todas
    as unidades já lançadas contam). NÃO usa duração nem phys_complete_pct.
    """
    if (a.unid_realizada or 0.0) <= 0 or not a.act_start:
        return 0.0
    if a.act_end and d >= a.act_end:
        return 1.0
    if d < a.act_start:
        return 0.0
    end_ref = a.act_end or data_date
    if end_ref <= a.act_start:
        return 1.0
    frac = (d - a.act_start).days / (end_ref - a.act_start).days
    return 1.0 if frac >= 1 else frac


def _acum(acts, d, data_date, modo) -> float:
    """% acumulado por UNIDADES FÍSICAS do PONDERADOR.

    Denominador = Σ peso (unidades orçadas).
    plan: Σ peso × fração planejada (programação atual do XER).
    real: Σ unid_realizada × fração temporal (act_reg_qty / target_qty).
    """
    W = sum(a.peso or 0.0 for a in acts)
    if W <= 0:
        return 0.0
    if modo == "plan":
        s = sum((a.peso or 0.0) * _planned_frac(a, d) for a in acts)
    else:
        s = sum((a.unid_realizada or 0.0) * _realized_time_frac(a, d, data_date) for a in acts)
    return round(s / W * 100, 2)


def _add_months(d: date, n: int) -> date:
    m = d.month - 1 + n
    y = d.year + m // 12
    return date(y, m % 12 + 1, 1)


def _meses(ini: date, fim: date) -> list[date]:
    out, cur = [], date(ini.year, ini.month, 1)
    while cur <= fim:
        out.append(cur)
        cur = _add_months(cur, 1)
    return out


# ── Dashboard ────────────────────────────────────────────────────────────────
def dashboard(db: Session) -> dict:
    projeto = get_projeto_ativo(db)
    if not projeto:
        return {"tem_dados": False}

    acts = db.query(ProdAtividade).filter(ProdAtividade.projeto_id == projeto.id).all()
    dd = projeto.data_date or date.today()

    # ── Total da obra = Σ unidades orçadas do PONDERADOR (≈ 1e9) ─────────
    W = sum(a.peso or 0.0 for a in acts)

    # ── Realizado e Tendência: 100% por UNIDADES do ponderador ──────────
    #   Realizado = Σ Actual Units ÷ total
    #   Tendência = Σ Remaining Units ÷ total
    real_acum = round(sum(a.unid_realizada or 0.0 for a in acts) / W * 100, 2) if W > 0 else 0.0
    tendencia = round(sum(a.unid_remaining or 0.0 for a in acts) / W * 100, 2) if W > 0 else 0.0

    # ── Previsto (BL Units) AUSENTE neste XER → gateado ──────────────────
    # Sem baseline/curva time-phased não há como calcular o Previsto.
    # Não usar duração nem programação atual (removidos por decisão).
    plan_acum = None
    spi = None
    classif = "indisponivel"

    d_sem = dd - timedelta(days=7)
    prev_mes = date(dd.year, dd.month, 1) - timedelta(days=1)

    # Realizado por período via datas reais das unidades (não usa duração/phys)
    real_sem = round(real_acum - _acum(acts, d_sem, dd, "real"), 2)
    real_mes = round(real_acum - _acum(acts, prev_mes, dd, "real"), 2)
    plan_sem = plan_mes = None

    # contagem de atividades
    cont = {"total": len(acts), "concluidas": 0, "em_andamento": 0, "nao_iniciadas": 0}
    for a in acts:
        if a.status == "concluida":
            cont["concluidas"] += 1
        elif a.status == "em_andamento":
            cont["em_andamento"] += 1
        else:
            cont["nao_iniciadas"] += 1

    # por disciplina
    por_disc: dict[str, list] = {}
    for a in acts:
        if a.disciplina:
            por_disc.setdefault(a.disciplina, []).append(a)
    disciplinas = []
    for nome, lst in por_disc.items():
        Wd = sum(x.peso or 0.0 for x in lst)
        if Wd <= 0:
            continue
        re = round(sum(x.unid_realizada or 0.0 for x in lst) / Wd * 100, 1)
        rem = round(sum(x.unid_remaining or 0.0 for x in lst) / Wd * 100, 1)
        disciplinas.append({"disciplina": nome, "atividades": len(lst), "peso": round(Wd, 0),
                            "planejado": None, "realizado": re, "tendencia": rem, "desvio": None})
    # ordena por PESO (relevância física), não por contagem de atividades
    disciplinas.sort(key=lambda x: -x["peso"])

    # tendência semanal (acumulado realizado por unidades; planejado aguardando BL)
    tend = []
    for k in range(7, -1, -1):
        d = dd - timedelta(days=7 * k)
        tend.append({"data": d.isoformat(), "planejado": None,
                     "realizado": _acum(acts, d, dd, "real")})

    # evolução mensal (acumulado realizado; planejado aguardando BL)
    evol = []
    for m in _meses(projeto.plan_start or dd, dd):
        ref = min(_add_months(m, 1) - timedelta(days=1), dd)
        evol.append({"mes": m.strftime("%Y-%m"), "planejado": None,
                     "realizado": _acum(acts, ref, dd, "real")})

    # curva S resumida (realizado por unidades; planejado aguardando BL)
    curva = []
    for m in _meses(projeto.plan_start or dd, projeto.plan_end or dd):
        ref = _add_months(m, 1) - timedelta(days=1)
        ponto = {"mes": m.strftime("%Y-%m"), "planejado": None}
        ponto["realizado"] = _acum(acts, min(ref, dd), dd, "real") if m <= date(dd.year, dd.month, 1) else None
        curva.append(ponto)

    # atividades críticas / atrasadas / marcos
    criticas = sorted([a for a in acts if a.critica and a.status != "concluida"],
                      key=lambda a: (a.total_float_hr if a.total_float_hr is not None else 0))[:12]
    atrasadas = sorted([a for a in acts if a.status != "concluida" and a.target_end and a.target_end < dd],
                       key=lambda a: a.target_end)[:12]
    marcos = sorted([a for a in acts if a.is_marco], key=lambda a: (a.target_end or date.max))

    def _ato(a):
        return {"task_code": a.task_code, "nome": a.nome, "disciplina": a.disciplina,
                "status": a.status, "phys_pct": round(a.phys_pct or 0, 1),
                "target_end": a.target_end.isoformat() if a.target_end else None,
                "float_dias": round(a.total_float_hr / 8, 1) if a.total_float_hr is not None else None,
                "responsavel": a.responsavel}

    return {
        "tem_dados": True,
        "projeto": {
            "nome": projeto.proj_short_name,
            "data_date": dd.isoformat(),
            "plan_start": projeto.plan_start.isoformat() if projeto.plan_start else None,
            "plan_end": projeto.plan_end.isoformat() if projeto.plan_end else None,
            "origem_arquivo": projeto.origem_arquivo,
        },
        "kpis": {
            "semana": {"planejado": plan_sem, "realizado": real_sem, "desvio": None},
            "mes": {"planejado": plan_mes, "realizado": real_mes, "desvio": None},
            "acumulado": {"planejado": plan_acum, "realizado": real_acum,
                          "tendencia": tendencia, "desvio": None},
            "spi": {"valor": spi, "classificacao": classif},
            "atividades": cont,
        },
        "disciplinas": disciplinas,
        "tendencia_semanal": tend,
        "evolucao_mensal": evol,
        "curva_s": curva,
        "criticas": [_ato(a) for a in criticas],
        "atrasadas": [_ato(a) for a in atrasadas],
        "marcos": [_ato(a) for a in marcos],
        "metodo": {
            "ponderacao": "Unidades Não Relacionadas à Mão de Obra (PONDERADOR URFCC)",
            "realizado": "Σ Actual Units ÷ total da obra",
            "tendencia": "Σ Remaining Units ÷ total da obra",
            "previsto": "Σ BL Units ÷ total da obra (BL ausente neste XER)",
            "total_obra": round(W, 0),
            "unid_realizada_total": round(sum(a.unid_realizada or 0.0 for a in acts), 0),
            "unid_remaining_total": round(sum(a.unid_remaining or 0.0 for a in acts), 0),
        },
        "aviso_planejado": ("Previsto/SPI/Desvio indisponíveis: as BL Units (Linha de Base) não "
                            "estão presentes neste XER (sem baseline nem curva time-phased). "
                            "Forneça o export de baseline ou a curva planejada para habilitá-los."),
        "previsto_disponivel": False,
        "sinais": {
            "marcos_no_xer": len(marcos),
            "com_responsavel": sum(1 for a in acts if a.responsavel),
            "sem_disciplina": sum(1 for a in acts if not a.disciplina),
            "sem_ponderador": sum(1 for a in acts if (a.peso or 0.0) <= 0),
            "baseline_separada": False,
        },
    }
