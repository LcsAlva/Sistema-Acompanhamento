"""Testes para `_persistir_tarefas` — função crítica do fluxo de import.

Cobertura mínima:
  * Insere tarefas novas e cria QCRON
  * Reimport preserva estado QPROG (no_qprog, datas, observações)
  * Auto-QREAL quando atividade do QPROG anterior chega a 100%
  * Sub-tarefas preservadas entre importações
  * Adiantadas reinseridas quando ainda não concluídas
  * Filtro por disciplina
  * Linhas sem activity_id são ignoradas

Os testes usam SQLite in-memory via fixture `db` e chamam o helper
diretamente (sem subir FastAPI).
"""
from datetime import date

from backend.models import Semana, Tarefa, ProgramacaoSemanal, SubTarefa
from backend.routers.imports import _persistir_tarefas


def _semana(db, codigo="S_37", inicio="2026-04-20", fim="2026-04-26"):
    s = Semana(
        codigo=codigo,
        data_inicio=date.fromisoformat(inicio),
        data_fim=date.fromisoformat(fim),
    )
    db.add(s); db.commit(); db.refresh(s)
    return s


def _raw(activity_id, **kw):
    """Constrói um dict de tarefa raw como sai dos parsers XLSX/XER."""
    base = {
        "activity_id": activity_id,
        "nome": f"Atividade {activity_id}",
        "disciplina": "Civil",
        "supervisor": "Sup A",
        "encarregado": "Enc",
        "area_unidade": "TGV",
        "duracao": 5,
        "inicio_lb":   date(2026, 4, 18),
        "termino_lb":  date(2026, 4, 25),
        "inicio_prog": date(2026, 4, 20),
        "termino_prog": date(2026, 4, 24),
        "pct_avanco":  0.0,
        "pct_executado": 0.0,
    }
    base.update(kw)
    return base


# ──────────────────────────────────────────────────────────────────────
# Casos
# ──────────────────────────────────────────────────────────────────────

def test_import_inicial_cria_tarefas_e_qcron(db):
    semana = _semana(db)
    raws = [_raw("URFCC-001"), _raw("URFCC-002")]

    res = _persistir_tarefas(raws, semana, db)

    assert res["tarefas_novas"] == 2
    assert res["tarefas_atualizadas"] == 0
    assert res["qcron_count"] == 2
    assert db.query(Tarefa).count() == 2
    progs = db.query(ProgramacaoSemanal).all()
    assert len(progs) == 2
    assert all(not p.no_qprog for p in progs)
    assert all(not p.qreal_concluida for p in progs)


def test_reimport_preserva_estado_qprog(db):
    semana = _semana(db)
    _persistir_tarefas([_raw("URFCC-001")], semana, db)

    # Planejador marca a atividade no QPROG e adiciona observação
    prog = db.query(ProgramacaoSemanal).first()
    prog.no_qprog = True
    prog.observacoes = "Aguardando liberação"
    prog.inicio_qprog = date(2026, 4, 21)
    prog.termino_qprog = date(2026, 4, 23)
    db.commit()

    # Reimporta o mesmo XER — datas do cronograma podem mudar
    raws = [_raw("URFCC-001", inicio_prog=date(2026, 4, 21), termino_prog=date(2026, 4, 25))]
    _persistir_tarefas(raws, semana, db)

    prog2 = db.query(ProgramacaoSemanal).first()
    assert prog2.no_qprog is True
    assert prog2.observacoes == "Aguardando liberação"
    assert prog2.inicio_qprog == date(2026, 4, 21)
    assert prog2.termino_qprog == date(2026, 4, 23)


def test_auto_qreal_quando_atividade_chega_a_100(db):
    semana = _semana(db)
    _persistir_tarefas([_raw("URFCC-001")], semana, db)

    # Marca como QPROG
    prog = db.query(ProgramacaoSemanal).first()
    prog.no_qprog = True
    db.commit()

    # Reimport com pct_executado=100 e datas fora da janela
    # (sai do novo QCRON, deveria virar auto-QREAL)
    raws = [_raw(
        "URFCC-001",
        pct_executado=100.0,
        pct_avanco=100.0,
        inicio_prog=date(2026, 4, 1),
        termino_prog=date(2026, 4, 10),  # antes da semana
    )]
    res = _persistir_tarefas(raws, semana, db)

    assert res["auto_qreal_count"] == 1
    prog2 = db.query(ProgramacaoSemanal).first()
    assert prog2.qreal_concluida is True
    assert prog2.pct_qreal == 100.0


def test_sub_tarefas_preservadas_entre_importacoes(db):
    semana = _semana(db)
    _persistir_tarefas([_raw("URFCC-001")], semana, db)

    prog = db.query(ProgramacaoSemanal).first()
    prog.no_qprog = True
    db.add(SubTarefa(
        programacao_id=prog.id,
        descricao="Solda 1",
        status="concluida",
        inicio_qprog=date(2026, 4, 21),
        termino_qprog=date(2026, 4, 22),
    ))
    db.add(SubTarefa(programacao_id=prog.id, descricao="Solda 2", status="parcial"))
    db.commit()

    _persistir_tarefas([_raw("URFCC-001")], semana, db)

    prog2 = db.query(ProgramacaoSemanal).first()
    subs = db.query(SubTarefa).filter(SubTarefa.programacao_id == prog2.id).all()
    descricoes = sorted(s.descricao for s in subs)
    assert descricoes == ["Solda 1", "Solda 2"]
    solda1 = next(s for s in subs if s.descricao == "Solda 1")
    assert solda1.status == "concluida"
    assert solda1.inicio_qprog == date(2026, 4, 21)


def test_adiantadas_reinseridas_quando_nao_concluiu(db):
    semana = _semana(db)
    _persistir_tarefas([_raw("URFCC-001")], semana, db)

    prog = db.query(ProgramacaoSemanal).first()
    prog.no_qprog = True
    prog.adiantada = True
    prog.semana_original = "S_38"
    db.commit()

    # Reimport: cronograma move a tarefa para fora da semana atual,
    # mas pct ainda < 100 — deve ser reinserida como adiantada.
    raws = [_raw(
        "URFCC-001",
        inicio_prog=date(2026, 5, 1),
        termino_prog=date(2026, 5, 5),
        pct_executado=50.0,
    )]
    _persistir_tarefas(raws, semana, db)

    prog2 = db.query(ProgramacaoSemanal).filter(ProgramacaoSemanal.semana == "S_37").first()
    assert prog2 is not None
    assert prog2.adiantada is True
    assert prog2.semana_original == "S_38"


def test_filtro_por_disciplina(db):
    semana = _semana(db)
    raws = [
        _raw("URFCC-CIV-001", disciplina="Civil"),
        _raw("URFCC-CAL-001", disciplina="Caldeiraria"),
        _raw("URFCC-ELE-001", disciplina="Elétrica"),
    ]
    res = _persistir_tarefas(raws, semana, db, disciplinas_filtro=["Civil", "Caldeiraria"])

    assert res["qcron_count"] == 2
    progs = db.query(ProgramacaoSemanal).all()
    discs = sorted(p.tarefa.disciplina for p in progs)
    assert discs == ["Caldeiraria", "Civil"]


def test_linhas_sem_activity_id_sao_ignoradas(db):
    semana = _semana(db)
    raws = [
        _raw("URFCC-001"),
        {"activity_id": None, "nome": "lixo"},
        {"activity_id": "", "nome": "vazio"},
        _raw("URFCC-002"),
    ]
    res = _persistir_tarefas(raws, semana, db)

    assert res["tarefas_novas"] == 2
    assert db.query(Tarefa).count() == 2


def test_atividade_concluida_sai_do_qcron_sem_estado_anterior(db):
    """Tarefa que vem 100% no primeiro import nunca entrou no QPROG —
    não deve gerar programacao_semanal nem auto-QREAL."""
    semana = _semana(db)
    raws = [_raw("URFCC-001", pct_executado=100.0, pct_avanco=100.0)]

    res = _persistir_tarefas(raws, semana, db)

    assert res["qcron_count"] == 0
    assert res["auto_qreal_count"] == 0
    assert db.query(ProgramacaoSemanal).count() == 0
    # A tarefa em si foi persistida (cadastro mestre)
    assert db.query(Tarefa).count() == 1
