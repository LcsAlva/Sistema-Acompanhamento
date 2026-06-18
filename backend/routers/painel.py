"""
Endpoint do Painel de Avanço Físico.
GET  /api/painel/{semana}             — retorna todos os dados do painel.
POST /api/painel/{semana}/importar    — importa XER e recalcula (independente da Prog. Semanal).
POST /api/painel/{semana}/recalcular  — recalcula sem reimportar.
"""
import logging
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from ..database import get_db

logger = logging.getLogger(__name__)
from ..models import PainelSnapshot, PainelFaseSemana, Semana, Tarefa
from ..services.painel_calc import FASE_MAP, calcular_painel

router = APIRouter(prefix="/painel", tags=["painel"])

# Ordem de exibição das fases no painel
FASE_ORDER = [
    "MOBILIZAÇÃO",
    "ENG. DETALHAMENTO",
    "CONSTRUÇÃO CIVIL",
    "MONTAGEM ELETROMECÂNICA",
    "COMISSIONAMENTO",
    "FORNECIMENTO DE BENS",
]


@router.get("/{semana}")
def get_painel(semana: str, db: Session = Depends(get_db)):
    semana_obj = db.query(Semana).filter(Semana.codigo == semana).first()
    if not semana_obj:
        raise HTTPException(status_code=404, detail=f"Semana '{semana}' não encontrada.")

    # ── Snapshot da semana atual ─────────────────────────────────────────────
    snap_atual = db.query(PainelSnapshot).filter(PainelSnapshot.semana == semana).first()
    fases_atual = {
        f.fase: f for f in db.query(PainelFaseSemana).filter(PainelFaseSemana.semana == semana).all()
    }

    # ── Semana anterior (comparativo) ───────────────────────────────────────
    semanas_todas = db.query(Semana).order_by(Semana.data_inicio).all()
    idx = next((i for i, s in enumerate(semanas_todas) if s.codigo == semana), -1)
    semana_ant = semanas_todas[idx - 1] if idx > 0 else None
    fases_ant = {}
    if semana_ant:
        fases_ant = {
            f.fase: f for f in db.query(PainelFaseSemana).filter(PainelFaseSemana.semana == semana_ant.codigo).all()
        }

    # ── Fases ────────────────────────────────────────────────────────────────
    fases_out = []
    for fase in FASE_ORDER:
        f = fases_atual.get(fase)
        fases_out.append({
            "fase": fase,
            "prev": round(f.pct_prev_lb, 2) if f else None,
            "real": round(f.pct_real, 2) if f else None,
            "desvio": round(f.pct_real - f.pct_prev_lb, 2) if f else None,
            "total": False,
        })

    # Total geral
    total_prev = snap_atual.avanco_prev_lb if snap_atual else None
    total_real = snap_atual.avanco_real if snap_atual else None
    fases_out.append({
        "fase": "AVANÇO DO PROJETO",
        "prev": round(total_prev, 2) if total_prev is not None else None,
        "real": round(total_real, 2) if total_real is not None else None,
        "desvio": round(total_real - total_prev, 2) if (total_real is not None and total_prev is not None) else None,
        "total": True,
    })

    # ── Comparativo ─────────────────────────────────────────────────────────
    comp_out = []
    semana_ant_cod = semana_ant.codigo if semana_ant else "—"
    for fase in FASE_ORDER:
        f_ant = fases_ant.get(fase)
        f_at  = fases_atual.get(fase)
        comp_out.append({
            "fase": fase,
            "s_ant": round(f_ant.pct_real - f_ant.pct_prev_lb, 2) if f_ant else None,
            "s_at":  round(f_at.pct_real  - f_at.pct_prev_lb,  2) if f_at  else None,
        })
    # Total
    snap_ant = db.query(PainelSnapshot).filter(PainelSnapshot.semana == semana_ant.codigo).first() if semana_ant else None
    comp_out.append({
        "fase": "AVANÇO DO PROJETO",
        "s_ant": round((snap_ant.avanco_real or 0) - (snap_ant.avanco_prev_lb or 0), 2) if snap_ant else None,
        "s_at":  round((total_real or 0) - (total_prev or 0), 2) if total_real is not None else None,
        "total": True,
    })

    # ── S-curve semanal (todos os snapshots ordenados por data) ──────────────
    all_snaps = (
        db.query(PainelSnapshot, Semana)
        .join(Semana, PainelSnapshot.semana == Semana.codigo)
        .order_by(Semana.data_inicio)
        .all()
    )

    semanal_out = []
    prev_real_ac = 0.0
    prev_prev_ac = 0.0
    meses_pt = ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez']
    for snap, sem in all_snaps:
        r = snap.avanco_real if snap.avanco_real is not None else None
        p = snap.avanco_prev_lb if snap.avanco_prev_lb is not None else None
        try:
            d = sem.data_fim
            nome = f"{d.day:02d}-{meses_pt[d.month - 1]}"
        except (AttributeError, IndexError, TypeError):
            # data_fim pode ser None ou string inválida; mantém o código da semana como rótulo.
            nome = sem.codigo

        real_sem = round(r - prev_real_ac, 2) if r is not None else None
        prev_sem = round(p - prev_prev_ac, 2) if p is not None else None
        semanal_out.append({
            "nome":    nome,
            "semana":  sem.codigo,
            "prev":    prev_sem,
            "real":    real_sem,
            "prevAc":  round(p, 2) if p is not None else None,
            "realAc":  round(r, 2) if r is not None else None,
        })
        if r is not None:
            prev_real_ac = r
        if p is not None:
            prev_prev_ac = p

    # ── S-curve mensal (agrupa por mês) ──────────────────────────────────────
    from collections import defaultdict
    meses_data = defaultdict(lambda: {"prev_ac": None, "real_ac": None, "data_fim": None})
    for snap, sem in all_snaps:
        if not sem.data_fim:
            continue
        try:
            mes_key = f"{meses_pt[sem.data_fim.month - 1]}/{str(sem.data_fim.year)[2:]}"
        except (AttributeError, IndexError, TypeError):
            continue
        # Guarda o último (mais recente) valor do mês
        if snap.avanco_prev_lb is not None:
            meses_data[mes_key]["prev_ac"] = snap.avanco_prev_lb
        if snap.avanco_real is not None:
            meses_data[mes_key]["real_ac"] = snap.avanco_real
        meses_data[mes_key]["data_fim"] = sem.data_fim

    geral_out = []
    prev_real_m = 0.0
    prev_prev_m = 0.0
    for mes, d in sorted(meses_data.items(), key=lambda x: x[1]["data_fim"] or date.min):
        p_ac = round(d["prev_ac"], 2) if d["prev_ac"] is not None else None
        r_ac = round(d["real_ac"], 2) if d["real_ac"] is not None else None
        geral_out.append({
            "nome":    mes,
            "prevSem": round(p_ac - prev_prev_m, 2) if p_ac is not None else None,
            "realSem": round(r_ac - prev_real_m, 2) if r_ac is not None else None,
            "prevAc":  p_ac,
            "realAc":  r_ac,
        })
        if r_ac is not None:
            prev_real_m = r_ac
        if p_ac is not None:
            prev_prev_m = p_ac

    # ── KPIs ─────────────────────────────────────────────────────────────────
    kpis = {
        "linha_base":    round(total_prev, 2) if total_prev is not None else None,
        "prev_semana":   semanal_out[-1]["prev"] if semanal_out else None,
        "real_ac":       round(total_real, 2) if total_real is not None else None,
        "desvio_ac":     round(total_real - total_prev, 2) if (total_real is not None and total_prev is not None) else None,
        "semana_ant":    semana_ant_cod,
    }

    return {
        "semana":      semana,
        "kpis":        kpis,
        "fases":       fases_out,
        "comparativo": comp_out,
        "semanal":     semanal_out,
        "geral":       geral_out,
        "semana_ant":  semana_ant_cod,
        "calculado":   snap_atual is not None,
    }


@router.post("/{semana}/recalcular")
def recalcular_painel(semana: str, db: Session = Depends(get_db)):
    """Força recálculo do painel para uma semana específica."""
    semana_obj = db.query(Semana).filter(Semana.codigo == semana).first()
    if not semana_obj:
        raise HTTPException(status_code=404, detail=f"Semana '{semana}' não encontrada.")
    result = calcular_painel(semana_obj, db)
    return {"ok": True, **result}


@router.post("/{semana}/importar")
async def importar_xer_painel(
    semana: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Importa um XER exclusivamente para o Painel de Avanço Físico.
    Atualiza pct_avanco e unid_orcadas_smo em todas as tarefas,
    depois recalcula o painel. NÃO altera QCRON/QPROG/QREAL.
    """
    from ..parsers.xer_parser import parse_xer

    semana_obj = db.query(Semana).filter(Semana.codigo == semana).first()
    if not semana_obj:
        raise HTTPException(status_code=404, detail=f"Semana '{semana}' não encontrada.")

    conteudo = await file.read()
    try:
        tarefas_raw = parse_xer(conteudo.decode("latin-1"))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Erro ao ler XER: {e}")

    # Atualiza apenas pct_avanco e unid_orcadas_smo — não toca em QCRON/QPROG
    atualizadas = 0
    novas = 0
    for t in tarefas_raw:
        activity_id = t.get("activity_id")
        if not activity_id:
            continue
        tarefa = db.query(Tarefa).filter(Tarefa.activity_id == activity_id).first()
        if tarefa:
            tarefa.pct_avanco       = t.get("pct_avanco", 0.0) or 0.0
            if t.get("unid_orcadas_smo") is not None:
                tarefa.unid_orcadas_smo = t["unid_orcadas_smo"]
            # Atualiza também disciplina e LB caso ainda não tenham
            if not tarefa.disciplina and t.get("disciplina"):
                tarefa.disciplina = t["disciplina"]
            if not tarefa.inicio_lb and t.get("inicio_lb"):
                tarefa.inicio_lb = t["inicio_lb"]
            if not tarefa.termino_lb and t.get("termino_lb"):
                tarefa.termino_lb = t["termino_lb"]
            if not tarefa.duracao and t.get("duracao"):
                tarefa.duracao = t["duracao"]
            atualizadas += 1
        else:
            # Tarefa nova: persiste com dados mínimos para o cálculo
            db.add(Tarefa(
                activity_id=activity_id,
                nome=t.get("nome", activity_id),
                disciplina=t.get("disciplina"),
                duracao=t.get("duracao"),
                inicio_lb=t.get("inicio_lb"),
                termino_lb=t.get("termino_lb"),
                inicio_atual=t.get("inicio_prog"),
                termino_atual=t.get("termino_prog"),
                pct_avanco=t.get("pct_avanco", 0.0) or 0.0,
                unid_orcadas_smo=t.get("unid_orcadas_smo"),
                area_unidade=t.get("area_unidade"),
                wbs_codigo=t.get("wbs_codigo"),
                wbs_path=t.get("wbs_path"),
            ))
            novas += 1

    db.commit()

    # Recalcula o painel com os dados atualizados
    result = calcular_painel(semana_obj, db)

    return {
        "ok": True,
        "tarefas_atualizadas": atualizadas,
        "tarefas_novas": novas,
        "semana": semana,
        **result,
    }
