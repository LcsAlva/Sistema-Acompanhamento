"""Testes do Motor de Medição de Engenharia (Módulo 2 — Fase 2A)."""
from datetime import datetime, timedelta

from backend.models import LdDocumento, LdHistoricoStatus, SigemDocumento
from backend.services import motor_medicao_service as motor


def _add(db, codigo, status, disciplina="CIVIL", a4=1.0):
    d = LdDocumento(codigo_documento=codigo, status=status, disciplina=disciplina,
                    a4_equivalente=a4)
    db.add(d)
    db.flush()
    return d


def test_sem_workflow_conta_como_apto(db):
    assert motor.is_apto("SEM WORKFLOW") is True
    assert motor.is_apto("sem  workflow") is True   # normalização
    assert motor.is_apto("EM ANALISE") is False


def test_dashboard_contagens_e_pct(db):
    _add(db, "D1", "SEM WORKFLOW", a4=2.0)
    _add(db, "D2", "EM ELABORACAO", a4=1.0)
    _add(db, "D3", "EM ANALISE", a4=1.0)
    db.commit()
    dash = motor.dashboard(db)
    assert dash["documentos_totais"] == 3
    assert dash["sem_workflow"] == 1
    assert dash["em_elaboracao"] == 1
    assert dash["em_analise"] == 1
    # peso por A4: 2.0 apto / 4.0 total = 0.5
    assert dash["pct_medido"] == 0.5
    assert dash["a4_acumulado"] == 2.0
    assert dash["a4_total"] == 4.0


def test_dashboard_usa_status_sigem_quando_existe(db):
    _add(db, "D1", "EM ANALISE", a4=2.0)
    db.add(SigemDocumento(codigo_documento="D1", status="SEM WORKFLOW", revisao="B"))
    db.commit()

    dash = motor.dashboard(db)

    assert dash["sem_workflow"] == 1
    assert dash["pct_medido"] == 1.0
    assert dash["status_origem_sigem"] == 1
    assert dash["status_origem_ld"] == 0


def test_por_disciplina_usa_a4(db):
    _add(db, "C1", "SEM WORKFLOW", disciplina="CIVIL", a4=3.0)
    _add(db, "C2", "EM ANALISE", disciplina="CIVIL", a4=1.0)
    _add(db, "T1", "SEM WORKFLOW", disciplina="TUBULACAO", a4=5.0)
    db.commit()
    res = {r["disciplina"]: r for r in motor.medicao_por_disciplina(db)}
    assert res["CIVIL"]["pct_medicao"] == 0.75      # 3/4
    assert res["TUBULACAO"]["pct_medicao"] == 1.0   # 5/5
    assert res["CIVIL"]["docs_medidos"] == 1


def test_fallback_contagem_quando_sem_a4(db):
    _add(db, "X1", "SEM WORKFLOW", a4=0)
    _add(db, "X2", "EM ANALISE", a4=0)
    db.commit()
    dash = motor.dashboard(db)
    assert dash["peso_por"] == "contagem"
    assert dash["pct_medido"] == 0.5   # 1 de 2 docs


def test_evolucao_semanal_a_partir_do_historico(db):
    d = _add(db, "E1", "SEM WORKFLOW", a4=1.0)
    # histórico: virou SEM WORKFLOW há 1 dia (esta semana)
    db.add(LdHistoricoStatus(
        documento_id=d.id, status_anterior="EM ANALISE", status_novo="SEM WORKFLOW",
        data_alteracao=datetime.now() - timedelta(days=1),
    ))
    db.commit()
    serie = motor.evolucao_semanal(db, semanas=4)
    assert len(serie) == 4
    # na última semana o doc está apto
    assert serie[-1]["sem_workflow"] == 1
    # numa semana muito anterior à transição, não estava apto
    assert serie[0]["sem_workflow"] == 0
