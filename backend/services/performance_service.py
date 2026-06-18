from __future__ import annotations

import json
from datetime import date, timedelta

from sqlalchemy.orm import Session

from ..models import (
    EconomicoImportacao,
    EconomicoResumoCalculado,
    PerformanceAuditoriaMes,
    PerformanceCustoClassificacao,
    ProdAtividade,
    ProdProjeto,
)


CLASSIFICACOES_PADRAO = [
    ("Salários, H.e, transf, adic M.O.D", "proporcional", "mao_de_obra_direta", "Tende a acompanhar avanço físico, mas pode antecipar ou atrasar por histograma."),
    ("Salários, H.e, transf, adic M.O.I", "hibrido", "mao_de_obra_indireta", "Parte acompanha obra; parte é estrutura mínima e pode distorcer eficiência física."),
    ("Rescisões / Indenizações", "nao_proporcional", "desmobilizacao", "Evento trabalhista pontual; não representa avanço físico."),
    ("Custos c/Pessoal ( VR, VT, Plano saude, etc )", "hibrido", "beneficios", "Acompanha efetivo, mas não necessariamente produção executada."),
    ("Encargos, férias e 13°", "hibrido", "encargos", "Segue folha e provisões, podendo ter descasamento com produção."),
    ("Provisão Desmobilização da Obra", "nao_proporcional", "mobilizacao_desmobilizacao", "Provisão temporal; pode gerar falsa leitura de custo por avanço."),
    ("Provisão de férias e 13°", "nao_proporcional", "provisao", "Provisão contábil, não avanço físico."),
    ("Materiais de Aplicação", "hibrido", "compras_antecipadas", "Compra pode ocorrer antes da instalação física."),
    ("Materiais de Consumo", "hibrido", "consumo_operacional", "Pode acompanhar campo, mas estoque/antecipação distorcem."),
    ("Veículos Maquinas e Equipamentos", "hibrido", "equipamentos", "Mobilização e locação podem ocorrer antes do avanço físico."),
    ("Serviços de Terceiros", "proporcional", "servicos", "Tende a acompanhar execução, mas contratos por mobilização podem antecipar custo."),
    ("Custos com Canteiro de Obra", "nao_proporcional", "mobilizacao", "Canteiro e estrutura não crescem linearmente com avanço físico."),
    ("Despesas Administrativas", "nao_proporcional", "administrativo", "Custo de suporte; não deve medir eficiência física diretamente."),
    ("Despesas de Viagens", "hibrido", "viagens_fretes", "Pode refletir mobilização, fretes ou apoio, não produção direta."),
    ("Depreciação e Amortização", "nao_proporcional", "contabil", "Critério contábil, não físico."),
    ("Créditos PIS/COFINS", "nao_proporcional", "tributario", "Efeito fiscal; não representa produção."),
    ("Imobilizado", "nao_proporcional", "imobilizado", "Aquisição patrimonial pode antecipar uso em campo."),
]


RISCOS_PADRAO = [
    "Compras antecipadas podem elevar custo antes do avanço físico.",
    "Mobilização e canteiro não evoluem linearmente com o percentual físico.",
    "Compra para revenda pode distorcer custo por avanço físico.",
    "Custos administrativos são estrutura de suporte e não medem produção direta.",
    "Fretes e viagens podem ocorrer antes ou depois da execução associada.",
]


def obter_auditoria_integrada(db: Session, recalcular: bool = False) -> dict:
    imp = db.query(EconomicoImportacao).order_by(EconomicoImportacao.importado_em.desc()).first()
    if not imp:
        return {"disponivel": False, "motivo": "Nenhuma importacao economica encontrada."}

    projeto = (
        db.query(ProdProjeto)
        .filter(ProdProjeto.ativo.is_(True))
        .order_by(ProdProjeto.importado_em.desc())
        .first()
    )

    if recalcular or not _tem_auditoria(db, imp.id, projeto.id if projeto else None):
        gerar_auditoria_integrada(db, imp, projeto)

    rows = (
        db.query(PerformanceAuditoriaMes)
        .filter(PerformanceAuditoriaMes.importacao_id == imp.id)
        .order_by(PerformanceAuditoriaMes.mes)
        .all()
    )
    classificacoes = (
        db.query(PerformanceCustoClassificacao)
        .filter(PerformanceCustoClassificacao.importacao_id == imp.id)
        .order_by(PerformanceCustoClassificacao.classificacao, PerformanceCustoClassificacao.categoria_dre)
        .all()
    )

    return {
        "disponivel": True,
        "importacao": {
            "id": imp.id,
            "arquivo_original": imp.arquivo_original,
            "importado_em": imp.importado_em,
        },
        "producao": {
            "projeto_id": projeto.id if projeto else None,
            "nome": projeto.proj_short_name if projeto else None,
            "data_date": projeto.data_date.isoformat() if projeto and projeto.data_date else None,
            "fonte": "prod_atividade ativo por Ponderador URFCC" if projeto else "sem projeto ativo",
        },
        "validacao_mensal": [_auditoria_mes_dict(r) for r in rows],
        "classificacao_custos": [_classificacao_dict(r) for r in classificacoes],
        "riscos_interpretacao": RISCOS_PADRAO,
        "modelagem": {
            "granularidade": "mes",
            "relacao": "competencia mensal: ultimo avanço fisico acumulado do mes vs acumulados economicos ate o mes",
            "fonte_fisica": "ProdAtividade.peso e ProdAtividade.unid_realizada do projeto ativo; fallback indisponivel quando nao houver XER ativo.",
            "fonte_economica": "economico_resumo_calculado tipo sistema/importacao auditada.",
            "restricao": "Nao calcula eficiencia por custo total nesta fase; apenas tabela de validacao e classificacao dos custos.",
        },
    }


def gerar_auditoria_integrada(db: Session, imp: EconomicoImportacao, projeto: ProdProjeto | None) -> None:
    projeto_id = projeto.id if projeto else None
    db.query(PerformanceAuditoriaMes).filter(PerformanceAuditoriaMes.importacao_id == imp.id).delete()
    db.query(PerformanceCustoClassificacao).filter(PerformanceCustoClassificacao.importacao_id == imp.id).delete()
    db.flush()

    for categoria, classificacao, comportamento, risco in CLASSIFICACOES_PADRAO:
        db.add(PerformanceCustoClassificacao(
            importacao_id=imp.id,
            categoria_dre=categoria,
            classificacao=classificacao,
            comportamento=comportamento,
            risco_interpretacao=risco,
            regra="Classificacao gerencial inicial por natureza da categoria DRE; nao altera valores financeiros.",
        ))

    econ_por_mes = _economico_acumulado_por_mes(db, imp.id)
    fisico_por_mes = _fisico_acumulado_por_mes(db, projeto) if projeto else {}
    for mes in sorted(econ_por_mes):
        econ = econ_por_mes[mes]
        fisico = fisico_por_mes.get(mes)
        riscos = _riscos_mes(econ, fisico)
        db.add(PerformanceAuditoriaMes(
            importacao_id=imp.id,
            projeto_id=projeto_id,
            mes=mes,
            avanco_fisico_pct=fisico,
            receita_acumulada=econ["receita"],
            custos_acumulados=econ["custos"],
            resultado_acumulado=econ["resultado"],
            fonte_fisica="prod_atividade ativo por Ponderador URFCC",
            fonte_economica="economico_resumo_calculado",
            riscos=json.dumps(riscos, ensure_ascii=False),
        ))
    db.commit()


def _tem_auditoria(db: Session, importacao_id: int, projeto_id: int | None) -> bool:
    q = db.query(PerformanceAuditoriaMes).filter(PerformanceAuditoriaMes.importacao_id == importacao_id)
    if projeto_id is not None:
        q = q.filter(PerformanceAuditoriaMes.projeto_id == projeto_id)
    return q.first() is not None


def _economico_acumulado_por_mes(db: Session, importacao_id: int) -> dict[date, dict]:
    rows = (
        db.query(EconomicoResumoCalculado)
        .filter(
            EconomicoResumoCalculado.importacao_id == importacao_id,
            EconomicoResumoCalculado.periodo.isnot(None),
            EconomicoResumoCalculado.categoria.is_(None),
            EconomicoResumoCalculado.cenario == "real",
        )
        .order_by(EconomicoResumoCalculado.periodo)
        .all()
    )
    por_mes: dict[date, dict] = {}
    for r in rows:
        bucket = por_mes.setdefault(r.periodo, {"receita": 0.0, "custos": 0.0, "resultado": 0.0})
        if r.indicador == "receita":
            bucket["receita"] += float(r.valor or 0)
        elif r.indicador in {"custos_diretos", "custos_indiretos", "impostos"}:
            bucket["custos"] += float(r.valor or 0)
        elif r.indicador == "resultado":
            bucket["resultado"] += float(r.valor or 0)

    acumulado = {"receita": 0.0, "custos": 0.0, "resultado": 0.0}
    out = {}
    for mes in sorted(por_mes):
        for key in acumulado:
            acumulado[key] += por_mes[mes][key]
        out[mes] = dict(acumulado)
    return out


def _fisico_acumulado_por_mes(db: Session, projeto: ProdProjeto) -> dict[date, float]:
    acts = db.query(ProdAtividade).filter(ProdAtividade.projeto_id == projeto.id).all()
    if not acts:
        return {}
    dd = projeto.data_date or date.today()
    start = projeto.plan_start or min((a.act_start or a.target_start or dd) for a in acts)
    months = _meses(start, dd)
    return {m: _acum_fisico(acts, min(_fim_mes(m), dd), dd) for m in months}


def _acum_fisico(acts: list[ProdAtividade], ref: date, data_date: date) -> float:
    total = sum(a.peso or 0.0 for a in acts)
    if total <= 0:
        return 0.0
    realizado = sum((a.unid_realizada or 0.0) * _realized_time_frac(a, ref, data_date) for a in acts)
    return round(realizado / total * 100, 4)


def _realized_time_frac(a: ProdAtividade, ref: date, data_date: date) -> float:
    if (a.unid_realizada or 0.0) <= 0 or not a.act_start:
        return 0.0
    if a.act_end and ref >= a.act_end:
        return 1.0
    if ref < a.act_start:
        return 0.0
    end_ref = a.act_end or data_date
    if end_ref <= a.act_start:
        return 1.0
    frac = (ref - a.act_start).days / (end_ref - a.act_start).days
    return max(0.0, min(frac, 1.0))


def _meses(ini: date, fim: date) -> list[date]:
    out = []
    cur = date(ini.year, ini.month, 1)
    limite = date(fim.year, fim.month, 1)
    while cur <= limite:
        out.append(cur)
        cur = _add_months(cur, 1)
    return out


def _add_months(d: date, n: int) -> date:
    m = d.month - 1 + n
    y = d.year + m // 12
    return date(y, m % 12 + 1, 1)


def _fim_mes(d: date) -> date:
    return _add_months(d, 1) - timedelta(days=1)


def _riscos_mes(econ: dict, fisico: float | None) -> list[str]:
    riscos = []
    if fisico in (None, 0) and abs(econ["custos"]) > 0:
        riscos.append("Custo acumulado com avanço físico inexistente ou não calculado.")
    if fisico is not None and fisico < 5 and abs(econ["custos"]) > 1_000_000:
        riscos.append("Custo relevante em baixo avanço físico: verificar compras antecipadas, mobilização ou revenda.")
    if econ["receita"] == 0 and abs(econ["custos"]) > 0:
        riscos.append("Custos lançados antes da receita realizada; comparação pode distorcer margem.")
    return riscos


def _auditoria_mes_dict(r: PerformanceAuditoriaMes) -> dict:
    return {
        "mes": r.mes.isoformat(),
        "avanco_fisico_pct": r.avanco_fisico_pct,
        "receita_acumulada": r.receita_acumulada,
        "custos_acumulados": r.custos_acumulados,
        "resultado_acumulado": r.resultado_acumulado,
        "fonte_fisica": r.fonte_fisica,
        "fonte_economica": r.fonte_economica,
        "riscos": json.loads(r.riscos or "[]"),
    }


def _classificacao_dict(r: PerformanceCustoClassificacao) -> dict:
    return {
        "categoria_dre": r.categoria_dre,
        "classificacao": r.classificacao,
        "comportamento": r.comportamento,
        "risco_interpretacao": r.risco_interpretacao,
        "regra": r.regra,
    }
