"""Testes do Achado B — alinhamento PV × EV na Curva-S / KPIs.

Cobre:
  - PV restrito ao ESCOPO MEDIDO (folhas no snapshot do BM), não ao contrato;
  - escopo PROGRESSIVO por competência (folha só conta a partir do BM dela);
  - correção do back-fill do EV (0 antes do 1º BM; carrega o último valor, não o final);
  - SPI apples-to-apples e campo de cobertura.
"""
import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.models import EapItem, BmCiclo, BmSnapshotPrevisao, BmConsolidado
from backend.services import bm_service as svc


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False)
    s = Session()
    yield s
    s.close()


def _eap(db):
    """EAP: 1 (nível 1) -> folhas 1.1 e 1.2, ambas com baseline mensal."""
    db.add_all([
        EapItem(codigo="1", descricao="Contrato", nivel=1, valor=1000.0,
                dist_mensal=json.dumps({"2026-04-01": 0.0, "2026-05-01": 500.0,
                                        "2026-06-01": 500.0, "2026-07-01": 0.0})),
        EapItem(codigo="1.1", descricao="A", nivel=2, parent_codigo="1", valor=600.0,
                dist_mensal=json.dumps({"2026-05-01": 300.0, "2026-06-01": 300.0})),
        EapItem(codigo="1.2", descricao="B", nivel=2, parent_codigo="1", valor=400.0,
                dist_mensal=json.dumps({"2026-05-01": 200.0, "2026-06-01": 200.0})),
    ])
    db.commit()


def _bm_fechado(db, ano, mes, snapshot_folhas, consolidado):
    """Cria um BM fechado com snapshot (escopo) e consolidado (medido) por folha.

    snapshot_folhas: lista de códigos de folha previstos no BM.
    consolidado: {codigo: valor_acumulado} para folhas (medido acumulado).
    """
    c = BmCiclo(ano=ano, mes=mes, status=svc.STATUS_FECHADA, numero_bm=f"BM-{ano}-{mes:02d}")
    db.add(c); db.flush()
    for cod in snapshot_folhas:
        db.add(BmSnapshotPrevisao(ciclo_id=c.id, eap_codigo=cod, pct_previsto=0.5))
    # consolidado materializa todas as folhas (medidas e não medidas)
    for cod in ("1.1", "1.2"):
        db.add(BmConsolidado(ciclo_id=c.id, eap_codigo=cod, is_folha=True, nivel=2,
                             valor_acumulado=consolidado.get(cod, 0.0)))
    db.commit()
    return c


def _ponto(pontos, iso):
    return next(p for p in pontos if p["data"] == iso)


# ═══════════════════════════════════════════════════════════════════════════
# PV restrito ao escopo medido + EV sem back-fill
# ═══════════════════════════════════════════════════════════════════════════

def test_pv_restrito_ao_escopo_medido(db):
    """Só a folha 1.1 entra no BM; o baseline de 1.2 NÃO deve contar no PV."""
    _eap(db)
    # BM 2026/05 mede só 1.1 (acumulado 180); 1.2 nunca é medida
    _bm_fechado(db, 2026, 5, snapshot_folhas=["1.1"], consolidado={"1.1": 180.0})

    pontos = svc.get_curva_s_consolidada(db)
    p05 = _ponto(pontos, "2026-05-01")

    # PV = baseline de 1.1 até 05 (300), NÃO 300+200(1.2)=500
    assert p05["pv_acum"] == pytest.approx(300.0)
    assert p05["ev_acum"] == pytest.approx(180.0)


def test_escopo_progressivo_por_competencia(db):
    """1.2 só entra no escopo quando seu BM (2026/06) é fechado."""
    _eap(db)
    _bm_fechado(db, 2026, 5, snapshot_folhas=["1.1"], consolidado={"1.1": 180.0})
    _bm_fechado(db, 2026, 6, snapshot_folhas=["1.2"], consolidado={"1.1": 180.0, "1.2": 100.0})

    pontos = svc.get_curva_s_consolidada(db)
    p05 = _ponto(pontos, "2026-05-01")
    p06 = _ponto(pontos, "2026-06-01")

    # Em 05: escopo {1.1} -> PV = 300
    assert p05["pv_acum"] == pytest.approx(300.0)
    # Em 06: escopo {1.1,1.2} -> PV = (300+300) + (200+200) = 1000
    assert p06["pv_acum"] == pytest.approx(1000.0)
    # EV em 06 = 1.1(180) + 1.2(100) = 280
    assert p06["ev_acum"] == pytest.approx(280.0)


def test_ev_sem_backfill(db):
    """EV deve ser 0 antes do 1º BM e CARREGAR o último valor (não o total final)."""
    _eap(db)
    _bm_fechado(db, 2026, 5, snapshot_folhas=["1.1"], consolidado={"1.1": 180.0})

    pontos = svc.get_curva_s_consolidada(db)
    # Antes do 1º BM: EV e PV zerados (escopo vazio)
    assert _ponto(pontos, "2026-04-01")["ev_acum"] == 0.0
    assert _ponto(pontos, "2026-04-01")["pv_acum"] == 0.0
    # No mês do BM
    assert _ponto(pontos, "2026-05-01")["ev_acum"] == pytest.approx(180.0)
    # Mês posterior sem BM: carrega o último EV conhecido (180), não back-fill estranho
    assert _ponto(pontos, "2026-06-01")["ev_acum"] == pytest.approx(180.0)


def test_ev_monotonico_nao_decrescente(db):
    """A curva de EV acumulado nunca deve regredir ao longo do tempo."""
    _eap(db)
    _bm_fechado(db, 2026, 5, snapshot_folhas=["1.1"], consolidado={"1.1": 180.0})
    _bm_fechado(db, 2026, 6, snapshot_folhas=["1.2"], consolidado={"1.1": 180.0, "1.2": 100.0})

    pontos = svc.get_curva_s_consolidada(db)
    evs = [p["ev_acum"] for p in pontos]
    assert evs == sorted(evs), f"EV acumulado regrediu: {evs}"


# ═══════════════════════════════════════════════════════════════════════════
# KPIs — SPI apples-to-apples + cobertura
# ═══════════════════════════════════════════════════════════════════════════

def test_kpis_spi_apples_to_apples_e_cobertura(db):
    """SPI = EV/PV no MESMO universo (escopo medido); cobertura reflete o BAC."""
    _eap(db)
    _bm_fechado(db, 2026, 5, snapshot_folhas=["1.1"], consolidado={"1.1": 150.0})

    k = svc.get_kpis_dashboard(db)
    assert k["competencia_referencia"] == "2026/05"
    # PV(escopo) em 05 = 300; EV = 150 -> SPI = 0.5
    assert k["pv"] == pytest.approx(300.0)
    assert k["ev"] == pytest.approx(150.0)
    assert k["spi"] == pytest.approx(0.5, abs=1e-3)
    # BAC = 1000; cobertura = valor de 1.1 (600) / 1000 = 60%
    assert k["bac"] == pytest.approx(1000.0)
    assert k["cobertura_escopo_pct"] == pytest.approx(60.0, abs=0.01)


def test_kpis_sem_bm_retorna_vazio_com_campos(db):
    """Sem BM fechado: KPIs zerados, mas com todos os campos (inclui cobertura)."""
    _eap(db)
    k = svc.get_kpis_dashboard(db)
    for campo in ("bac", "pv", "ev", "spi", "pct_pv", "pct_ev",
                  "competencia_referencia", "cobertura_escopo_pct",
                  "bac_escopo", "eac", "vac"):
        assert campo in k
    assert k["ev"] == 0.0
    assert k["spi"] == 0.0


# ═══════════════════════════════════════════════════════════════════════════
# Achado C — EAC/VAC sobre o orçamento do ESCOPO MEDIDO (não o BAC do contrato)
# ═══════════════════════════════════════════════════════════════════════════

def test_eac_vac_usam_orcamento_do_escopo_nao_o_contrato(db):
    """EAC/VAC devem usar o orçamento do escopo medido, não o BAC do contrato."""
    _eap(db)
    # Escopo = {1.1} (orçamento R$ 600). PV(05)=300, EV=150 -> SPI=0,5.
    _bm_fechado(db, 2026, 5, snapshot_folhas=["1.1"], consolidado={"1.1": 150.0})
    k = svc.get_kpis_dashboard(db)

    assert k["bac"] == pytest.approx(1000.0)          # BAC do contrato (informativo)
    assert k["bac_escopo"] == pytest.approx(600.0)    # orçamento do escopo (folha 1.1)
    assert k["spi"] == pytest.approx(0.5, abs=1e-3)
    # EAC = bac_escopo / SPI = 600 / 0,5 = 1200 ; VAC = 600 - 1200 = -600
    assert k["eac"] == pytest.approx(1200.0, abs=1.0)
    assert k["vac"] == pytest.approx(-600.0, abs=1.0)
    # NÃO pode usar o contrato: EAC com BAC seria 1000/0,5 = 2000 (VAC -1000)
    assert k["eac"] != pytest.approx(2000.0, abs=1.0)


def test_vac_proporcional_ao_escopo_nao_explode(db):
    """VAC fica na escala do escopo medido, não na escala do contrato."""
    _eap(db)
    _bm_fechado(db, 2026, 5, snapshot_folhas=["1.1"], consolidado={"1.1": 150.0})
    k = svc.get_kpis_dashboard(db)
    # |VAC| não pode ultrapassar a escala do escopo (<= bac_escopo aqui)
    assert abs(k["vac"]) <= k["bac_escopo"] * 2  # 600 -> EAC 1200, VAC -600
    assert abs(k["vac"]) < k["bac"]              # muito menor que o contrato (1000)


def test_eac_vac_spi_zero_nao_quebra(db):
    """SPI=0 (PV>0, EV=0): EAC cai para o orçamento do escopo, VAC=0, sem divisão por zero."""
    _eap(db)
    # Escopo {1.1} previsto, porém medido = 0 -> EV=0, PV=300 -> SPI=0
    _bm_fechado(db, 2026, 5, snapshot_folhas=["1.1"], consolidado={"1.1": 0.0})
    k = svc.get_kpis_dashboard(db)
    assert k["ev"] == 0.0
    assert k["spi"] == 0.0
    assert k["eac"] == pytest.approx(600.0)   # fallback = orçamento do escopo
    assert k["vac"] == pytest.approx(0.0)
