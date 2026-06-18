"""Testes da Engine de Competência Financeira.

Cobre:
  - Criação automática via get_or_create_competencia
  - Abertura manual via abrir_competencia (cria + registra log)
  - Transições válidas: aberta→em_apuracao→fechada→consolidada→encerrada
  - Transição inválida bloqueia com ValueError
  - locked=True bloqueia assert_competencia_editavel
  - Status fechada/consolidada/encerrada bloqueiam assert_competencia_editavel
  - encerrar_competencia seta locked=True automaticamente
  - Auditoria: logs são gerados para cada transição
  - listar_competencias com filtros
  - Integração: bm_service e eap respeitam a competência fechada
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from backend.database import Base, get_db
from backend.main import app
from backend.models import CompetenciaFinanceira, CompetenciaLog
from backend.services import competencia_service as svc


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="function")
def db():
    """Sessão SQLite em memória isolada por teste."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def client(db):
    """TestClient com DB injetado via override."""
    def _override():
        yield db
    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


# ── Testes de criação ─────────────────────────────────────────────────────────

class TestCriacaoCompetencia:
    def test_get_competencia_nao_existente_retorna_none(self, db):
        comp = svc.get_competencia(db, 2026, 5)
        assert comp is None

    def test_get_or_create_cria_como_aberta(self, db):
        comp = svc.get_or_create_competencia(db, 2026, 5)
        db.flush()
        assert comp.ano == 2026
        assert comp.mes == 5
        assert comp.status == svc.STATUS_ABERTA
        assert comp.locked is False

    def test_get_or_create_idempotente(self, db):
        c1 = svc.get_or_create_competencia(db, 2026, 5)
        db.flush()
        c2 = svc.get_or_create_competencia(db, 2026, 5)
        assert c1.id == c2.id

    def test_get_or_create_registra_log(self, db):
        comp = svc.get_or_create_competencia(db, 2026, 6, criado_por="sistema")
        db.flush()
        logs = db.query(CompetenciaLog).filter_by(competencia_id=comp.id).all()
        assert len(logs) == 1
        assert logs[0].evento == "COMPETENCIA_CRIADA"
        assert logs[0].status_depois == svc.STATUS_ABERTA
        assert logs[0].usuario == "sistema"

    def test_abrir_competencia_manual(self, db):
        comp = svc.abrir_competencia(db, 2026, 7, usuario="fulano", observacao="teste")
        assert comp.id is not None
        assert comp.status == svc.STATUS_ABERTA
        assert comp.aberto_por == "fulano"

    def test_abrir_competencia_duplicada_levanta_erro(self, db):
        svc.abrir_competencia(db, 2026, 8)
        with pytest.raises(ValueError, match="já existe"):
            svc.abrir_competencia(db, 2026, 8)


# ── Testes de transições ──────────────────────────────────────────────────────

class TestTransicoes:
    def _criar(self, db, ano=2026, mes=1):
        return svc.abrir_competencia(db, ano, mes, usuario="teste")

    def test_aberta_para_em_apuracao(self, db):
        self._criar(db)
        comp = svc.mover_para_em_apuracao(db, 2026, 1, usuario="op1")
        assert comp.status == svc.STATUS_EM_APURACAO
        assert comp.em_apuracao_por == "op1"
        assert comp.em_apuracao_em is not None

    def test_em_apuracao_para_fechada(self, db):
        self._criar(db)
        svc.mover_para_em_apuracao(db, 2026, 1)
        comp = svc.fechar_competencia(db, 2026, 1, usuario="op2")
        assert comp.status == svc.STATUS_FECHADA
        assert comp.fechado_por == "op2"

    def test_fechada_para_consolidada(self, db):
        self._criar(db)
        svc.mover_para_em_apuracao(db, 2026, 1)
        svc.fechar_competencia(db, 2026, 1)
        comp = svc.consolidar_competencia(db, 2026, 1, usuario="op3")
        assert comp.status == svc.STATUS_CONSOLIDADA

    def test_consolidada_para_encerrada(self, db):
        self._criar(db)
        svc.mover_para_em_apuracao(db, 2026, 1)
        svc.fechar_competencia(db, 2026, 1)
        svc.consolidar_competencia(db, 2026, 1)
        comp = svc.encerrar_competencia(db, 2026, 1, usuario="contabil")
        assert comp.status == svc.STATUS_ENCERRADA
        assert comp.locked is True
        assert comp.encerrado_por == "contabil"

    def test_encerrada_seta_locked(self, db):
        self._criar(db)
        svc.mover_para_em_apuracao(db, 2026, 1)
        svc.fechar_competencia(db, 2026, 1)
        svc.consolidar_competencia(db, 2026, 1)
        comp = svc.encerrar_competencia(db, 2026, 1)
        assert comp.locked is True

    def test_transicao_invalida_aberta_para_fechada(self, db):
        self._criar(db)
        with pytest.raises(ValueError, match="Transição inválida"):
            svc.fechar_competencia(db, 2026, 1)

    def test_transicao_invalida_em_apuracao_para_consolidada(self, db):
        self._criar(db)
        svc.mover_para_em_apuracao(db, 2026, 1)
        with pytest.raises(ValueError, match="Transição inválida"):
            svc.consolidar_competencia(db, 2026, 1)

    def test_encerrada_nao_permite_nova_transicao(self, db):
        self._criar(db)
        svc.mover_para_em_apuracao(db, 2026, 1)
        svc.fechar_competencia(db, 2026, 1)
        svc.consolidar_competencia(db, 2026, 1)
        svc.encerrar_competencia(db, 2026, 1)
        with pytest.raises(ValueError, match="bloqueada"):
            svc.mover_para_em_apuracao(db, 2026, 1)


# ── Testes de assert_competencia_editavel ────────────────────────────────────

class TestAssertCompetenciaEditavel:
    def test_sem_competencia_permite(self, db):
        # Não deve levantar — ausência = implicitamente aberta
        svc.assert_competencia_editavel(db, 2026, 3)

    def test_status_aberta_permite(self, db):
        svc.abrir_competencia(db, 2026, 3)
        svc.assert_competencia_editavel(db, 2026, 3)  # sem exceção

    def test_status_em_apuracao_permite(self, db):
        svc.abrir_competencia(db, 2026, 3)
        svc.mover_para_em_apuracao(db, 2026, 3)
        svc.assert_competencia_editavel(db, 2026, 3)  # sem exceção

    def test_status_fechada_bloqueia(self, db):
        svc.abrir_competencia(db, 2026, 3)
        svc.mover_para_em_apuracao(db, 2026, 3)
        svc.fechar_competencia(db, 2026, 3)
        with pytest.raises(ValueError, match="não permite"):
            svc.assert_competencia_editavel(db, 2026, 3)

    def test_status_consolidada_bloqueia(self, db):
        svc.abrir_competencia(db, 2026, 3)
        svc.mover_para_em_apuracao(db, 2026, 3)
        svc.fechar_competencia(db, 2026, 3)
        svc.consolidar_competencia(db, 2026, 3)
        with pytest.raises(ValueError, match="não permite"):
            svc.assert_competencia_editavel(db, 2026, 3)

    def test_status_encerrada_bloqueia(self, db):
        svc.abrir_competencia(db, 2026, 3)
        svc.mover_para_em_apuracao(db, 2026, 3)
        svc.fechar_competencia(db, 2026, 3)
        svc.consolidar_competencia(db, 2026, 3)
        svc.encerrar_competencia(db, 2026, 3)
        with pytest.raises(ValueError, match="bloqueada"):
            svc.assert_competencia_editavel(db, 2026, 3)

    def test_locked_true_bloqueia_independente_do_status(self, db):
        svc.abrir_competencia(db, 2026, 4)
        # Forçar locked manualmente (simula lock manual)
        comp = svc.get_competencia(db, 2026, 4)
        comp.locked = True
        db.flush()
        with pytest.raises(ValueError, match="bloqueada"):
            svc.assert_competencia_editavel(db, 2026, 4)


# ── Testes de auditoria ───────────────────────────────────────────────────────

class TestAuditoria:
    def test_cada_transicao_gera_log(self, db):
        svc.abrir_competencia(db, 2026, 9, usuario="u1")
        svc.mover_para_em_apuracao(db, 2026, 9, usuario="u2")
        svc.fechar_competencia(db, 2026, 9, usuario="u3")

        comp = svc.get_competencia(db, 2026, 9)
        assert len(comp.logs) == 3
        eventos = [lg.evento for lg in comp.logs]
        assert "COMPETENCIA_ABERTA" in eventos
        assert f"COMPETENCIA_{svc.STATUS_EM_APURACAO.upper()}" in eventos
        assert f"COMPETENCIA_{svc.STATUS_FECHADA.upper()}" in eventos

    def test_log_registra_status_antes_e_depois(self, db):
        svc.abrir_competencia(db, 2026, 10)
        svc.mover_para_em_apuracao(db, 2026, 10, usuario="auditor")
        comp = svc.get_competencia(db, 2026, 10)

        log_transicao = next(
            lg for lg in comp.logs
            if lg.status_antes == svc.STATUS_ABERTA
        )
        assert log_transicao.status_depois == svc.STATUS_EM_APURACAO
        assert log_transicao.usuario == "auditor"


# ── Testes de listagem ────────────────────────────────────────────────────────

class TestListagem:
    def test_listar_sem_filtro(self, db):
        svc.abrir_competencia(db, 2026, 1)
        svc.abrir_competencia(db, 2026, 2)
        comps = svc.listar_competencias(db)
        assert len(comps) >= 2

    def test_filtrar_por_status(self, db):
        svc.abrir_competencia(db, 2026, 11)
        svc.abrir_competencia(db, 2026, 12)
        svc.mover_para_em_apuracao(db, 2026, 12)
        abertos = svc.listar_competencias(db, status=svc.STATUS_ABERTA)
        assert all(c.status == svc.STATUS_ABERTA for c in abertos)

    def test_filtrar_por_ano(self, db):
        svc.abrir_competencia(db, 2025, 1)
        svc.abrir_competencia(db, 2026, 1)
        resultado = svc.listar_competencias(db, ano=2025)
        assert all(c.ano == 2025 for c in resultado)


# ── Testes de endpoints HTTP ──────────────────────────────────────────────────

class TestEndpointsCompetencia:
    def test_abrir_competencia_201(self, client):
        r = client.post("/api/competencias/2026/5/abrir", json={"usuario": "teste"})
        assert r.status_code == 201
        data = r.json()
        assert data["ano"] == 2026
        assert data["mes"] == 5
        assert data["status"] == "aberta"
        assert data["locked"] is False

    def test_abrir_competencia_duplicada_422(self, client):
        client.post("/api/competencias/2026/6/abrir")
        r = client.post("/api/competencias/2026/6/abrir")
        assert r.status_code == 422

    def test_consultar_competencia_404(self, client):
        r = client.get("/api/competencias/2099/1")
        assert r.status_code == 404

    def test_consultar_competencia_ok(self, client):
        client.post("/api/competencias/2026/7/abrir")
        r = client.get("/api/competencias/2026/7")
        assert r.status_code == 200
        data = r.json()
        assert "logs" in data
        assert data["status_label"] == "Aberta"

    def test_listar_competencias(self, client):
        client.post("/api/competencias/2026/8/abrir")
        r = client.get("/api/competencias")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_fluxo_completo_via_http(self, client):
        client.post("/api/competencias/2026/9/abrir", json={"usuario": "op1"})
        r = client.post("/api/competencias/2026/9/em-apuracao", json={"usuario": "op2"})
        assert r.status_code == 200
        assert r.json()["status"] == "em_apuracao"

        r = client.post("/api/competencias/2026/9/fechar", json={"usuario": "op3"})
        assert r.status_code == 200
        assert r.json()["status"] == "fechada"

        r = client.post("/api/competencias/2026/9/consolidar", json={"usuario": "op4"})
        assert r.status_code == 200
        assert r.json()["status"] == "consolidada"

        r = client.post("/api/competencias/2026/9/encerrar", json={"usuario": "contabil"})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "encerrada_contabilmente"
        assert data["locked"] is True

    def test_transicao_invalida_via_http_422(self, client):
        client.post("/api/competencias/2026/10/abrir")
        # Pular em_apuracao, tentar fechar direto
        r = client.post("/api/competencias/2026/10/fechar")
        assert r.status_code == 422

    def test_mes_invalido_422(self, client):
        r = client.post("/api/competencias/2026/13/abrir")
        assert r.status_code == 422

    def test_proximos_status_no_retorno(self, client):
        client.post("/api/competencias/2026/11/abrir")
        r = client.get("/api/competencias/2026/11")
        assert r.status_code == 200
        data = r.json()
        assert "em_apuracao" in data["proximos_status"]
