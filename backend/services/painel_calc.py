"""
Serviço de cálculo automático do Painel de Avanço Físico.
Chamado após cada importação de XER/XLSX.

Usa TODAS as tarefas do projeto (não apenas o QCRON da semana),
ponderando pelo peso SMO (unid_orcadas_smo) ou duração como fallback.
"""
from datetime import date
from sqlalchemy.orm import Session
from ..models import Tarefa, Semana, PainelSnapshot, PainelFaseSemana

# Mapeamento disciplina (campo no banco) → nome exibido no painel
FASE_MAP = {
    "Mobilização":                "MOBILIZAÇÃO",
    "Engenharia de detalhamento": "ENG. DETALHAMENTO",
    "Construção Civil":           "CONSTRUÇÃO CIVIL",
    "Eletromecânica":             "MONTAGEM ELETROMECÂNICA",
    "Comissionamento":            "COMISSIONAMENTO",
    "Fornecimento de bens":       "FORNECIMENTO DE BENS",
}


def calcular_painel(semana_obj: Semana, db: Session):
    """
    Calcula avanço físico por fase e snapshot total para a semana.
    Usa TODAS as tarefas cadastradas (atualizado a cada import de XER).
    Salva/atualiza painel_snapshot e painel_fase_semana.
    """
    ref_date = semana_obj.data_fim  # data de referência para cálculo do previsto LB

    # Todas as tarefas do projeto com disciplina mapeável
    todas_tarefas = db.query(Tarefa).all()

    fases: dict[str, dict] = {}
    total_real_num = 0.0
    total_prev_num = 0.0
    total_peso     = 0.0

    for tarefa in todas_tarefas:
        disciplina = tarefa.disciplina
        if not disciplina or disciplina not in FASE_MAP:
            continue

        fase_nome = FASE_MAP[disciplina]

        # Peso: SMO (horas/unidades orçadas) > duração em dias > 1
        peso = float(tarefa.unid_orcadas_smo or tarefa.duracao or 1)

        # % real físico atual (vem do phys_complete_pct do P6)
        pct_real = float(tarefa.pct_avanco or 0.0)

        # % previsto LB para a data de referência
        pct_prev = _calc_lb_pct(tarefa.inicio_lb, tarefa.termino_lb, ref_date)

        if fase_nome not in fases:
            fases[fase_nome] = {"sum_real": 0.0, "sum_prev": 0.0, "sum_peso": 0.0}

        fases[fase_nome]["sum_real"]  += pct_real * peso
        fases[fase_nome]["sum_prev"]  += pct_prev * peso
        fases[fase_nome]["sum_peso"]  += peso

        total_real_num += pct_real * peso
        total_prev_num += pct_prev * peso
        total_peso     += peso

    # Percentuais por fase
    resultado_fases = {}
    for fase, d in fases.items():
        sp = d["sum_peso"]
        resultado_fases[fase] = {
            "pct_real":    round(d["sum_real"] / sp, 4) if sp > 0 else 0.0,
            "pct_prev_lb": round(d["sum_prev"] / sp, 4) if sp > 0 else 0.0,
            "peso_total":  round(sp, 4),
        }

    avanco_real    = round(total_real_num / total_peso, 4) if total_peso > 0 else 0.0
    avanco_prev_lb = round(total_prev_num / total_peso, 4) if total_peso > 0 else 0.0

    # ── Persiste snapshot total ──────────────────────────────────────────────
    snap = db.query(PainelSnapshot).filter(PainelSnapshot.semana == semana_obj.codigo).first()
    if snap:
        snap.avanco_real     = avanco_real
        snap.avanco_prev_lb  = avanco_prev_lb
        snap.data_referencia = ref_date
    else:
        snap = PainelSnapshot(
            semana=semana_obj.codigo,
            data_referencia=ref_date,
            avanco_real=avanco_real,
            avanco_prev_lb=avanco_prev_lb,
        )
        db.add(snap)

    # ── Persiste fases ───────────────────────────────────────────────────────
    db.query(PainelFaseSemana).filter(PainelFaseSemana.semana == semana_obj.codigo).delete()
    for fase, d in resultado_fases.items():
        db.add(PainelFaseSemana(
            semana=semana_obj.codigo,
            fase=fase,
            pct_real=d["pct_real"],
            pct_prev_lb=d["pct_prev_lb"],
            peso_total=d["peso_total"],
        ))

    db.commit()
    return {
        "fases": resultado_fases,
        "avanco_real": avanco_real,
        "avanco_prev_lb": avanco_prev_lb,
    }


def _calc_lb_pct(inicio_lb, termino_lb, ref_date: date) -> float:
    """% planejado concluído até ref_date com base na linha de base."""
    if not inicio_lb or not termino_lb:
        return 0.0
    if ref_date >= termino_lb:
        return 100.0
    if ref_date <= inicio_lb:
        return 0.0
    total = (termino_lb - inicio_lb).days
    if total <= 0:
        return 100.0
    elapsed = (ref_date - inicio_lb).days
    return round(elapsed / total * 100, 4)
