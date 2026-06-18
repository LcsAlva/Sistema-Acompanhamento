"""Testes do serviço de Integração LD (Módulo 1 — Fase 2A)."""
from backend.models import LdDocumento, LdHistoricoStatus
from backend.services import ld_service as svc


def _row(codigo, status, disciplina="CIVIL", a4=1.0, titulo="Doc"):
    return {
        "codigo_documento": codigo, "titulo": titulo, "disciplina": disciplina,
        "revisao": "0", "status": status, "a4_equivalente": a4,
        "data_prevista": None, "data_emissao": None,
    }


def test_import_inicial_cria_documentos_e_transicao_inicial(db):
    res = svc.importar_ld(db, [_row("LD-1", "EM ELABORACAO"), _row("LD-2", "SEM WORKFLOW")], "ld_v1.xlsx")
    assert res["novos"] == 2
    assert res["status_alterados"] == 0
    assert db.query(LdDocumento).count() == 2
    # entrada inicial registrada como transição None → status
    assert db.query(LdHistoricoStatus).count() == 2


def test_reimport_com_mudanca_de_status_gera_historico(db):
    svc.importar_ld(db, [_row("LD-1", "EM ELABORACAO")], "ld_v1.xlsx")
    res = svc.importar_ld(db, [_row("LD-1", "SEM WORKFLOW")], "ld_v2.xlsx")
    assert res["status_alterados"] == 1
    assert res["novos"] == 0
    doc = db.query(LdDocumento).filter_by(codigo_documento="LD-1").first()
    assert doc.status == "SEM WORKFLOW"
    hist = svc.historico(db, doc.id)
    assert len(hist) == 2  # inicial + transição
    assert hist[-1].status_anterior is not None
    assert hist[-1].status_novo == "SEM WORKFLOW"
    assert hist[-1].arquivo_origem == "ld_v2.xlsx"


def test_reimport_identico_nao_gera_historico(db):
    svc.importar_ld(db, [_row("LD-1", "SEM WORKFLOW")], "ld_v1.xlsx")
    n_hist = db.query(LdHistoricoStatus).count()
    res = svc.importar_ld(db, [_row("LD-1", "SEM WORKFLOW")], "ld_v2.xlsx")
    assert res["status_alterados"] == 0
    assert db.query(LdHistoricoStatus).count() == n_hist  # nenhuma transição nova


def test_mudanca_so_de_grafia_nao_conta_como_transicao(db):
    svc.importar_ld(db, [_row("LD-1", "SEM WORKFLOW")], "v1.xlsx")
    res = svc.importar_ld(db, [_row("LD-1", "sem  workflow")], "v2.xlsx")  # caixa/espaços
    assert res["status_alterados"] == 0


def test_filtros_e_distintos(db):
    svc.importar_ld(db, [
        _row("LD-1", "SEM WORKFLOW", disciplina="CIVIL"),
        _row("LD-2", "EM ANALISE", disciplina="TUBULACAO"),
    ], "v1.xlsx")
    assert {d.codigo_documento for d in svc.listar_documentos(db, disciplina="CIVIL")} == {"LD-1"}
    assert {d.codigo_documento for d in svc.listar_documentos(db, status="EM ANALISE")} == {"LD-2"}
    assert svc.disciplinas_distintas(db) == ["CIVIL", "TUBULACAO"]
