"""Smoke tests do módulo Produção: parser XER + serviço de dashboard.

XER sintético mínimo com 1 projeto, WBS, código de disciplina e 2 atividades
(1 concluída, 1 em andamento) — valida extração, ponderação por duração e KPIs.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
import backend.models  # noqa: F401
from backend.parsers.xer_parser import extrair_producao
from backend.services import producao_service as svc

XER = "\t".join  # helper

_CONTEUDO = "\n".join([
    "%T\tPROJECT",
    "%F\tproj_id\tproj_short_name\tplan_start_date\tscd_end_date\tlast_recalc_date",
    "%R\t1\tOBRA-X\t2026-01-01 00:00\t2026-03-31 16:00\t2026-02-15 23:59",
    "%T\tACTVTYPE",
    "%F\tactv_code_type_id\tactv_code_type",
    "%R\t221\tURFCC-Disciplina",
    "%T\tACTVCODE",
    "%F\tactv_code_id\tactv_code_type_id\tactv_code_name\tshort_name",
    "%R\t9001\t221\tCivil\tCV",
    "%T\tTASKACTV",
    "%F\ttask_id\tactv_code_id\tactv_code_type_id",
    "%R\t101\t9001\t221",
    "%R\t102\t9001\t221",
    "%T\tPROJWBS",
    "%F\twbs_id\tparent_wbs_id\twbs_short_name\twbs_name\tproj_node_flag",
    "%R\t10\t\tOBRA-X\tObra X\tY",
    "%R\t11\t10\t1\tCivil\tN",
    "%T\tRSRC",
    "%F\trsrc_id\trsrc_name\trsrc_short_name\trsrc_type",
    "%R\t4652\tPONDERADOR URFCC\tPOND\tRT_Equip",
    "%R\t1370\tAJUDANTE\tAJ\tRT_Labor",
    "%T\tTASKRSRC",
    "%F\ttask_id\trsrc_id\ttarget_qty\tact_reg_qty\tremain_qty",
    "%R\t101\t4652\t1000\t1000\t0",
    "%R\t102\t4652\t1000\t300\t700",
    "%R\t101\t1370\t50\t40\t10",
    "%T\tTASK",
    "%F\ttask_id\twbs_id\ttask_code\ttask_name\tstatus_code\ttask_type\tphys_complete_pct\ttarget_drtn_hr_cnt\ttotal_float_hr_cnt\ttarget_start_date\ttarget_end_date\tact_start_date\tact_end_date",
    "%R\t101\t11\tA-001\tFundacao\tTK_Complete\tTT_Task\t100\t80\t\t2026-01-01 08:00\t2026-01-20 16:00\t2026-01-01 08:00\t2026-01-19 17:00",
    "%R\t102\t11\tA-002\tEstrutura\tTK_Active\tTT_Task\t50\t80\t0\t2026-02-01 08:00\t2026-02-28 16:00\t2026-02-03 08:00\t",
    "%E",
])


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng, autoflush=False)()
    yield s
    s.close()


def test_extrai_estrutura_real_do_xer():
    d = extrair_producao(_CONTEUDO)
    assert d["projeto"]["proj_short_name"] == "OBRA-X"
    assert d["projeto"]["data_date"].isoformat() == "2026-02-15"
    assert len(d["atividades"]) == 2
    assert d["disciplinas_detectadas"] == ["Civil"]
    a2 = next(a for a in d["atividades"] if a["task_code"] == "A-002")
    assert a2["disciplina"] == "Civil"
    assert a2["status"] == "em_andamento"
    assert a2["critica"] is True            # total_float = 0
    assert a2["peso"] == 1000                # unidades orçadas do PONDERADOR (não duração)
    assert a2["unid_realizada"] == 300       # act_reg_qty
    assert d["ponderador_encontrado"] is True
    assert d["peso_total"] == 2000           # só o ponderador (ignora o recurso de mão de obra)


def test_dashboard_kpis_ponderados_por_duracao(db):
    parsed = extrair_producao(_CONTEUDO)
    svc.importar_xer(db, parsed, "obra.xer")
    d = svc.dashboard(db)
    assert d["tem_dados"] is True
    # Realizado = Σ Actual Units / total = (1000+300)/2000 = 65%
    assert d["kpis"]["acumulado"]["realizado"] == 65.0
    # Tendência = Σ Remaining Units / total = (0+700)/2000 = 35%
    assert d["kpis"]["acumulado"]["tendencia"] == 35.0
    # Previsto GATEADO (BL ausente) → None; SPI/Desvio indisponíveis
    assert d["kpis"]["acumulado"]["planejado"] is None
    assert d["kpis"]["acumulado"]["desvio"] is None
    assert d["kpis"]["spi"]["valor"] is None
    assert d["kpis"]["spi"]["classificacao"] == "indisponivel"
    assert d["previsto_disponivel"] is False
    assert d["kpis"]["atividades"] == {"total": 2, "concluidas": 1, "em_andamento": 1, "nao_iniciadas": 0}
    # 1 disciplina (Civil); peso = 2000 (unidades do ponderador); realizado/tendência por unidades
    dc = d["disciplinas"][0]
    assert dc["disciplina"] == "Civil" and dc["peso"] == 2000
    assert dc["realizado"] == 65.0 and dc["tendencia"] == 35.0 and dc["planejado"] is None
    assert d["aviso_planejado"].startswith("Previsto/SPI/Desvio indispon")
    # 1 crítica (A-002), 0 marcos
    assert len(d["criticas"]) == 1 and d["criticas"][0]["task_code"] == "A-002"
    assert d["sinais"]["marcos_no_xer"] == 0


def test_reimport_substitui_projeto_ativo(db):
    parsed = extrair_producao(_CONTEUDO)
    svc.importar_xer(db, parsed, "v1.xer")
    svc.importar_xer(db, parsed, "v2.xer")
    ativos = [p for p in db.query(backend.models.ProdProjeto).all() if p.ativo]
    assert len(ativos) == 1 and ativos[0].origem_arquivo == "v2.xer"
