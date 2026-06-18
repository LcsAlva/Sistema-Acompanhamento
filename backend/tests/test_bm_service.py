"""Testes do fluxo completo do BmService — arquitetura hardened.

Cobertura:
  - Abertura de BM (com e sem previsão)
  - Lançamentos (validações de integridade)
  - Máquina de estados completa
  - Fechamento atômico
  - Consolidação
  - Geração de pendências
  - Redistribuição (parcial, total, bloqueios)
  - Imutabilidade (fechado, consolidado, snapshot)
  - Dashboard isolado de BMs abertos
  - Auditoria (BmLog)
  - Previsão (fechar, reabrir, convertida)
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.models import (
    EapItem, EapPrevisaoMensal,
    BmCiclo, BmSnapshotPrevisao, BmLancamento,
    BmVersao, BmConsolidado, BmPendencia, BmLog,
    CicloMedicao,
)
from backend.services import bm_service as svc


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def eap_basica(db):
    """EAP simples: 1 (nível 1) → 1.1 (folha)."""
    pai   = EapItem(codigo="1",   descricao="Contrato", nivel=1, valor=1_000_000.0)
    folha = EapItem(codigo="1.1", descricao="Serviços", nivel=2,
                    parent_codigo="1", valor=1_000_000.0)
    db.add_all([pai, folha])
    db.commit()
    return pai, folha


@pytest.fixture
def eap_dois_filhos(db):
    """EAP: 1 → 1.1 + 1.2 (duas folhas com valores distintos)."""
    pai  = EapItem(codigo="1",   descricao="Contrato",    nivel=1, valor=1_000_000.0)
    f1   = EapItem(codigo="1.1", descricao="Civil",       nivel=2,
                   parent_codigo="1", valor=600_000.0)
    f2   = EapItem(codigo="1.2", descricao="Elétrico",    nivel=2,
                   parent_codigo="1", valor=400_000.0)
    db.add_all([pai, f1, f2])
    db.commit()
    return pai, f1, f2


# ── Helpers de fluxo ─────────────────────────────────────────────────────────

def _abrir_bm_completo(db, eap_codigo, pct_previsto_pct, ano=2026, mes=5):
    """Cria previsão fechada e abre o BM (fluxo correto pós-hardening)."""
    db.add(EapPrevisaoMensal(
        ano=ano, mes=mes,
        eap_codigo=eap_codigo,
        pct_previsto=pct_previsto_pct,
        status_previsao="fechada",
    ))
    db.commit()
    return svc.abrir_bm(db, ano, mes, "planejador")


def _fechar_bm_completo(db, ciclo_id, usuario="gerente"):
    """Leva o BM por todo o fluxo de aprovação até fechar."""
    svc.transicionar_status(db, ciclo_id, svc.STATUS_EM_ANALISE, usuario)
    svc.transicionar_status(db, ciclo_id, svc.STATUS_PRE_APROVADA, usuario)
    return svc.fechar_bm(db, ciclo_id, usuario)


# ═══════════════════════════════════════════════════════════════════════════
# 1. ABERTURA DE BM — Ponto 2
# ═══════════════════════════════════════════════════════════════════════════

def test_abrir_bm_cria_ciclo_e_snapshot(db, eap_basica):
    """Abertura do BM cria BmCiclo e snapshot imutável da previsão."""
    _, folha = eap_basica
    ciclo = _abrir_bm_completo(db, folha.codigo, 20.0)

    assert ciclo.status == svc.STATUS_EM_PREVIA
    assert ciclo.numero_bm == "BM-2026-05"
    assert ciclo.ciclo_legado_id is not None

    snaps = db.query(BmSnapshotPrevisao).filter(
        BmSnapshotPrevisao.ciclo_id == ciclo.id
    ).all()
    assert len(snaps) == 1
    assert abs(snaps[0].pct_previsto - 0.20) < 1e-4

    prev = db.query(EapPrevisaoMensal).filter(
        EapPrevisaoMensal.ano == 2026, EapPrevisaoMensal.mes == 5,
        EapPrevisaoMensal.eap_codigo == folha.codigo,
    ).first()
    assert prev.status_previsao == "convertida"


def test_abrir_bm_sem_previsao_bloqueado(db, eap_basica):
    """BM NÃO pode ser aberto se não há nenhuma previsão lançada (Ponto 2)."""
    # Não há EapPrevisaoMensal para o mês — deve rejeitar
    with pytest.raises(ValueError, match="Não existe previsão mensal fechada"):
        svc.abrir_bm(db, 2026, 5)


def test_abrir_bm_exige_previsao_fechada(db, eap_basica):
    """Não deve abrir BM se a previsão ainda está em edição (Ponto 2)."""
    _, folha = eap_basica
    db.add(EapPrevisaoMensal(
        ano=2026, mes=5, eap_codigo=folha.codigo,
        pct_previsto=20.0,
        status_previsao="em_edicao",  # não fechada!
    ))
    db.commit()

    with pytest.raises(ValueError, match="em edição"):
        svc.abrir_bm(db, 2026, 5)


def test_abrir_bm_previsao_parcialmente_fechada_bloqueado(db, eap_dois_filhos):
    """BM bloqueado se ALGUM item da previsão ainda está em edição (Ponto 2)."""
    _, f1, f2 = eap_dois_filhos
    db.add(EapPrevisaoMensal(
        ano=2026, mes=5, eap_codigo=f1.codigo,
        pct_previsto=10.0, status_previsao="fechada",
    ))
    db.add(EapPrevisaoMensal(
        ano=2026, mes=5, eap_codigo=f2.codigo,
        pct_previsto=10.0, status_previsao="em_edicao",  # não fechada!
    ))
    db.commit()

    with pytest.raises(ValueError, match="em edição"):
        svc.abrir_bm(db, 2026, 5)


def test_abrir_bm_idempotente(db, eap_basica):
    """Abrir o mesmo mês duas vezes retorna o mesmo ciclo."""
    _, folha = eap_basica
    ciclo1 = _abrir_bm_completo(db, folha.codigo, 10.0)
    ciclo2 = svc.abrir_bm(db, 2026, 5)
    assert ciclo1.id == ciclo2.id


# ═══════════════════════════════════════════════════════════════════════════
# 2. LANÇAMENTOS
# ═══════════════════════════════════════════════════════════════════════════

def test_salvar_lancamentos_cria_versao(db, eap_basica):
    """Salvar lançamentos cria versão no audit trail."""
    _, folha = eap_basica
    ciclo = _abrir_bm_completo(db, folha.codigo, 20.0)

    svc.salvar_lancamentos(
        db, ciclo.id,
        [{"eap_codigo": folha.codigo, "pct_acumulado": 0.10}],
        "operador",
    )

    versoes = db.query(BmVersao).filter(BmVersao.ciclo_id == ciclo.id).all()
    assert len(versoes) == 1
    assert versoes[0].numero_versao == 1

    lancs = db.query(BmLancamento).filter(BmLancamento.ciclo_id == ciclo.id).all()
    assert len(lancs) == 1
    assert abs(lancs[0].pct_acumulado - 0.10) < 1e-4


def test_lancamento_rejeita_pct_acima_100(db, eap_basica):
    """pct_acumulado > 1.0 deve ser rejeitado."""
    _, folha = eap_basica
    ciclo = _abrir_bm_completo(db, folha.codigo, 10.0)

    with pytest.raises(ValueError, match="excede 100%|0% até 100%"):
        svc.salvar_lancamentos(
            db, ciclo.id,
            [{"eap_codigo": folha.codigo, "pct_acumulado": 1.5}],
        )


def test_lancamento_rejeita_regressao(db, eap_basica):
    """pct_acumulado < acumulado consolidado anterior deve ser rejeitado."""
    _, folha = eap_basica

    ciclo_mai = _abrir_bm_completo(db, folha.codigo, 30.0)
    svc.salvar_lancamentos(db, ciclo_mai.id, [{"eap_codigo": folha.codigo, "pct_acumulado": 0.30}])
    _fechar_bm_completo(db, ciclo_mai.id)

    db.add(EapPrevisaoMensal(
        ano=2026, mes=6, eap_codigo=folha.codigo,
        pct_previsto=10.0, status_previsao="fechada",
    ))
    db.commit()
    ciclo_jun = svc.abrir_bm(db, 2026, 6)

    with pytest.raises(ValueError, match="acumulado já consolidado"):
        svc.salvar_lancamentos(
            db, ciclo_jun.id,
            [{"eap_codigo": folha.codigo, "pct_acumulado": 0.20}],
        )


def test_lancamento_rejeita_item_nao_folha(db, eap_basica):
    """Lançar em item não-folha deve ser rejeitado."""
    pai, folha = eap_basica
    ciclo = _abrir_bm_completo(db, folha.codigo, 10.0)

    with pytest.raises(ValueError, match="não é folha"):
        svc.salvar_lancamentos(
            db, ciclo.id,
            [{"eap_codigo": pai.codigo, "pct_acumulado": 0.10}],
        )


def test_nao_permite_lancamento_em_bm_fechado(db, eap_basica):
    """BM fechado é imutável — não aceita lançamentos (Ponto 5)."""
    _, folha = eap_basica
    ciclo = _abrir_bm_completo(db, folha.codigo, 20.0)
    _fechar_bm_completo(db, ciclo.id)

    with pytest.raises(ValueError, match="não pode ser editado"):
        svc.salvar_lancamentos(
            db, ciclo.id,
            [{"eap_codigo": folha.codigo, "pct_acumulado": 0.5}],
        )


def test_nao_permite_lancamento_em_bm_consolidado(db, eap_basica):
    """BM consolidado é imutável — não aceita lançamentos (Ponto 5)."""
    _, folha = eap_basica
    ciclo = _abrir_bm_completo(db, folha.codigo, 20.0)
    _fechar_bm_completo(db, ciclo.id)
    svc.consolidar_bm(db, ciclo.id, "diretor")

    with pytest.raises(ValueError, match="não pode ser editado"):
        svc.salvar_lancamentos(
            db, ciclo.id,
            [{"eap_codigo": folha.codigo, "pct_acumulado": 0.9}],
        )


# ═══════════════════════════════════════════════════════════════════════════
# 3. MÁQUINA DE ESTADOS
# ═══════════════════════════════════════════════════════════════════════════

def test_fluxo_completo_aprovacao(db, eap_basica):
    """Fluxo completo: em_previa → analise → pre_aprovada → fechada."""
    _, folha = eap_basica
    ciclo = _abrir_bm_completo(db, folha.codigo, 10.0)
    assert ciclo.status == svc.STATUS_EM_PREVIA

    svc.transicionar_status(db, ciclo.id, svc.STATUS_EM_ANALISE, "analista")
    db.refresh(ciclo)
    assert ciclo.status == svc.STATUS_EM_ANALISE
    assert ciclo.enviado_analise_por == "analista"

    svc.transicionar_status(db, ciclo.id, svc.STATUS_PRE_APROVADA, "aprovador")
    db.refresh(ciclo)
    assert ciclo.status == svc.STATUS_PRE_APROVADA
    assert ciclo.pre_aprovado_por == "aprovador"

    svc.fechar_bm(db, ciclo.id, "gerente")
    db.refresh(ciclo)
    assert ciclo.status == svc.STATUS_FECHADA
    assert ciclo.fechado_por == "gerente"


def test_fechar_exige_pre_aprovada(db, eap_basica):
    """fechar_bm() deve rejeitar BM que não está em pre_aprovada."""
    _, folha = eap_basica
    ciclo = _abrir_bm_completo(db, folha.codigo, 10.0)

    with pytest.raises(ValueError, match="pre_aprovada"):
        svc.fechar_bm(db, ciclo.id, "gerente")

    svc.transicionar_status(db, ciclo.id, svc.STATUS_EM_ANALISE, "analista")
    with pytest.raises(ValueError, match="pre_aprovada"):
        svc.fechar_bm(db, ciclo.id, "gerente")


def test_retorno_de_status(db, eap_basica):
    """BM em analise pode retornar para em_previa."""
    _, folha = eap_basica
    ciclo = _abrir_bm_completo(db, folha.codigo, 10.0)
    svc.transicionar_status(db, ciclo.id, svc.STATUS_EM_ANALISE)
    svc.transicionar_status(db, ciclo.id, svc.STATUS_EM_PREVIA)
    db.refresh(ciclo)
    assert ciclo.status == svc.STATUS_EM_PREVIA


def test_status_endpoint_nao_permite_fechar(db, eap_basica):
    """O endpoint de status não deve permitir transição para 'fechada' (Ponto 2)."""
    _, folha = eap_basica
    ciclo = _abrir_bm_completo(db, folha.codigo, 10.0)
    svc.transicionar_status(db, ciclo.id, svc.STATUS_EM_ANALISE)
    svc.transicionar_status(db, ciclo.id, svc.STATUS_PRE_APROVADA)

    with pytest.raises(ValueError, match="endpoint de status"):
        svc.transicionar_status(db, ciclo.id, svc.STATUS_FECHADA)


def test_status_endpoint_nao_permite_consolidar(db, eap_basica):
    """O endpoint de status não deve permitir transição para 'consolidada'."""
    _, folha = eap_basica
    ciclo = _abrir_bm_completo(db, folha.codigo, 10.0)

    with pytest.raises(ValueError, match="endpoint de status"):
        svc.transicionar_status(db, ciclo.id, svc.STATUS_CONSOLIDADA)


def test_transicao_status_invalida(db, eap_basica):
    """Transição não permitida pela máquina de estados deve falhar."""
    _, folha = eap_basica
    ciclo = _abrir_bm_completo(db, folha.codigo, 10.0)

    with pytest.raises(ValueError, match="Transição"):
        svc.transicionar_status(db, ciclo.id, svc.STATUS_PRE_APROVADA)


def test_fechar_bm_duas_vezes_erro(db, eap_basica):
    """Fechar BM já fechado deve lançar erro."""
    _, folha = eap_basica
    ciclo = _abrir_bm_completo(db, folha.codigo, 10.0)
    _fechar_bm_completo(db, ciclo.id)

    with pytest.raises(ValueError, match="já está fechado"):
        svc.fechar_bm(db, ciclo.id, "gerente")


def test_consolidar_bm(db, eap_basica):
    """consolidar_bm() deve exigir status fechada."""
    _, folha = eap_basica
    ciclo = _abrir_bm_completo(db, folha.codigo, 10.0)

    with pytest.raises(ValueError, match="fechada"):
        svc.consolidar_bm(db, ciclo.id)

    _fechar_bm_completo(db, ciclo.id)
    svc.consolidar_bm(db, ciclo.id, "diretor")
    db.refresh(ciclo)
    assert ciclo.status == svc.STATUS_CONSOLIDADA
    assert ciclo.consolidado_por == "diretor"


def test_consolidar_duas_vezes_erro(db, eap_basica):
    """Consolidar BM já consolidado deve falhar."""
    _, folha = eap_basica
    ciclo = _abrir_bm_completo(db, folha.codigo, 10.0)
    _fechar_bm_completo(db, ciclo.id)
    svc.consolidar_bm(db, ciclo.id, "diretor")

    with pytest.raises(ValueError, match="já está consolidado"):
        svc.consolidar_bm(db, ciclo.id, "diretor")


# ═══════════════════════════════════════════════════════════════════════════
# 4. FECHAMENTO ATÔMICO (Ponto 6)
# ═══════════════════════════════════════════════════════════════════════════

def test_fechar_bm_materializa_consolidado(db, eap_basica):
    """Fechar BM deve materializar BmConsolidado com valores corretos."""
    _, folha = eap_basica
    ciclo = _abrir_bm_completo(db, folha.codigo, 15.0)
    svc.salvar_lancamentos(db, ciclo.id, [{"eap_codigo": folha.codigo, "pct_acumulado": 0.10}])
    _fechar_bm_completo(db, ciclo.id)

    cons = db.query(BmConsolidado).filter(BmConsolidado.ciclo_id == ciclo.id).all()
    assert len(cons) == 2  # folha + pai

    cons_folha = next(c for c in cons if c.eap_codigo == folha.codigo)
    assert abs(cons_folha.pct_acumulado - 0.10) < 1e-4
    assert abs(cons_folha.valor_periodo - 100_000.0) < 1.0


def test_fechamento_atomico_consolidado_imutavel(db, eap_basica):
    """BmConsolidado não pode ser recriado após fechamento (Ponto 5)."""
    _, folha = eap_basica
    ciclo = _abrir_bm_completo(db, folha.codigo, 15.0)
    svc.salvar_lancamentos(db, ciclo.id, [{"eap_codigo": folha.codigo, "pct_acumulado": 0.10}])
    _fechar_bm_completo(db, ciclo.id)

    # Tentar chamar _materializar_consolidado diretamente deve falhar
    with pytest.raises(ValueError, match="imutável"):
        svc._materializar_consolidado(db, ciclo)


def test_fechamento_atomico_pendencias_imutaveis(db, eap_basica):
    """Pendências não podem ser re-geradas após fechamento (Ponto 5)."""
    _, folha = eap_basica
    ciclo = _abrir_bm_completo(db, folha.codigo, 20.0)
    svc.salvar_lancamentos(db, ciclo.id, [{"eap_codigo": folha.codigo, "pct_acumulado": 0.10}])
    _fechar_bm_completo(db, ciclo.id)

    # Usa ASCII puro no match para evitar problemas de encoding no Windows
    with pytest.raises(ValueError, match="re-gerar"):
        svc._gerar_pendencias(db, ciclo)


# ═══════════════════════════════════════════════════════════════════════════
# 5. GERAÇÃO DE PENDÊNCIAS
# ═══════════════════════════════════════════════════════════════════════════

def test_fechar_bm_gera_pendencias(db, eap_basica):
    """Fechar BM deve gerar pendências quando previsto > medido no período."""
    _, folha = eap_basica
    ciclo = _abrir_bm_completo(db, folha.codigo, 20.0)
    svc.salvar_lancamentos(db, ciclo.id, [{"eap_codigo": folha.codigo, "pct_acumulado": 0.10}])
    _fechar_bm_completo(db, ciclo.id)

    pends = db.query(BmPendencia).filter(BmPendencia.ciclo_id == ciclo.id).all()
    assert len(pends) == 1
    pend = pends[0]
    assert abs(pend.pct_gap - 0.10) < 1e-4
    assert abs(pend.valor_gap - 100_000.0) < 1.0
    assert pend.status == "ativa"


def test_sem_pendencia_quando_medido_igual_previsto(db, eap_basica):
    """Não deve gerar pendência quando medido >= previsto."""
    _, folha = eap_basica
    ciclo = _abrir_bm_completo(db, folha.codigo, 15.0)
    svc.salvar_lancamentos(db, ciclo.id, [{"eap_codigo": folha.codigo, "pct_acumulado": 0.15}])
    _fechar_bm_completo(db, ciclo.id)

    pends = db.query(BmPendencia).filter(BmPendencia.ciclo_id == ciclo.id).all()
    assert len(pends) == 0


# ── Fixture que REPLICA a sessão de produção (autoflush=False) ────────────────
# CRÍTICO: backend/database.py cria SessionLocal com autoflush=False. A fixture
# `db` padrão usa autoflush=True (default do sessionmaker), o que MASCARAVA o bug
# de flush em _gerar_pendencias: com autoflush=True, a query do BmConsolidado
# disparava um flush automático que tornava as linhas recém-adicionadas visíveis.
# Em produção (autoflush=False) isso não acontecia e as pendências nunca eram
# geradas. Esta fixture garante que o teste exercite as MESMAS condições de prod.
@pytest.fixture
def db_prod():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = Session()
    assert session.autoflush is False  # garante que reproduz produção
    yield session
    session.close()


def test_REGRESSAO_pendencia_gerada_com_autoflush_false(db_prod):
    """REGRESSÃO: pendências DEVEM ser geradas mesmo com autoflush=False (prod).

    Bug original: em fechar_bm(), _materializar_consolidado() fazia db.add()
    sem flush; logo depois _gerar_pendencias() consultava BmConsolidado e, como
    a sessão de produção tem autoflush=False, NÃO enxergava as linhas pendentes
    → consolidados={} → toda folha caía em `if not cons: continue` → 0 pendências.

    O log gravava "pendencias_geradas: 0" e a tela Pendências ficava vazia mesmo
    havendo desvio (previsto > medido). Correção: db.flush() no início de
    _gerar_pendencias(). Este teste falha sem a correção.
    """
    db = db_prod
    pai = EapItem(codigo="1", descricao="Contrato", nivel=1, valor=1_000_000.0)
    folha = EapItem(codigo="1.1", descricao="Serviços", nivel=2,
                    parent_codigo="1", valor=1_000_000.0)
    db.add_all([pai, folha])
    db.commit()

    # Previsão 50%, medido 20% no período → gap 30% → pendência de R$ 300k
    db.add(EapPrevisaoMensal(ano=2026, mes=5, eap_codigo=folha.codigo,
                             pct_previsto=50.0, status_previsao="fechada"))
    db.commit()
    ciclo = svc.abrir_bm(db, 2026, 5, "planejador")
    svc.salvar_lancamentos(db, ciclo.id, [{"eap_codigo": folha.codigo, "pct_acumulado": 0.20}])
    svc.transicionar_status(db, ciclo.id, svc.STATUS_EM_ANALISE, "analista")
    svc.transicionar_status(db, ciclo.id, svc.STATUS_PRE_APROVADA, "aprovador")
    svc.fechar_bm(db, ciclo.id, "gerente")

    # A pendência DEVE existir e ser persistida (não só visível na sessão).
    pends = db.query(BmPendencia).filter(BmPendencia.ciclo_id == ciclo.id).all()
    assert len(pends) == 1, (
        "Pendência não gerada com autoflush=False — regressão do bug de flush "
        "em _gerar_pendencias()."
    )
    pend = pends[0]
    assert abs(pend.pct_gap - 0.30) < 1e-4
    assert abs(pend.valor_gap - 300_000.0) < 1.0
    assert pend.status == "ativa"

    # O log de fechamento deve refletir a quantidade correta (não 0).
    log_fechado = (db.query(BmLog)
                   .filter(BmLog.ciclo_id == ciclo.id, BmLog.evento == "BM_FECHADO")
                   .first())
    assert log_fechado is not None
    assert '"pendencias_geradas": 1' in (log_fechado.detalhe or ""), \
        "Log registrou pendencias_geradas != 1 — _gerar_pendencias retornou errado."

    # E o endpoint/serviço de exibição deve retorná-la.
    exibidas = svc.get_pendencias_ativas(db, ano=2026, mes=5)
    assert len(exibidas) == 1


def test_acumulado_correto_entre_bms(db, eap_basica):
    """BM seguinte deve ter pct_acum_anterior e pct_periodo corretos."""
    _, folha = eap_basica

    ciclo_mai = _abrir_bm_completo(db, folha.codigo, 10.0, mes=5)
    svc.salvar_lancamentos(db, ciclo_mai.id, [{"eap_codigo": folha.codigo, "pct_acumulado": 0.10}])
    _fechar_bm_completo(db, ciclo_mai.id)

    db.add(EapPrevisaoMensal(
        ano=2026, mes=6, eap_codigo=folha.codigo,
        pct_previsto=15.0, status_previsao="fechada",
    ))
    db.commit()
    ciclo_jun = svc.abrir_bm(db, 2026, 6)
    svc.salvar_lancamentos(db, ciclo_jun.id, [{"eap_codigo": folha.codigo, "pct_acumulado": 0.25}])
    _fechar_bm_completo(db, ciclo_jun.id)

    cons = (
        db.query(BmConsolidado)
        .filter(BmConsolidado.ciclo_id == ciclo_jun.id,
                BmConsolidado.eap_codigo == folha.codigo)
        .first()
    )
    assert abs(cons.pct_acumulado - 0.25) < 1e-4
    assert abs(cons.pct_periodo   - 0.15) < 1e-4
    assert abs(cons.valor_periodo - 150_000.0) < 1.0


# ═══════════════════════════════════════════════════════════════════════════
# 6. REDISTRIBUIÇÃO (Ponto 7)
# ═══════════════════════════════════════════════════════════════════════════

def test_redistribuir_pendencia_parcial(db, eap_basica):
    """Redistribuição parcial: 50% do saldo restante."""
    _, folha = eap_basica
    ciclo = _abrir_bm_completo(db, folha.codigo, 20.0)
    svc.salvar_lancamentos(db, ciclo.id, [{"eap_codigo": folha.codigo, "pct_acumulado": 0.10}])
    _fechar_bm_completo(db, ciclo.id)

    pend = db.query(BmPendencia).filter(BmPendencia.ciclo_id == ciclo.id).first()
    assert pend is not None  # gap = 10%

    svc.redistribuir_pendencia(db, pend.id, 2026, 6, 0.5, "planejador")
    db.refresh(pend)
    assert pend.status == "redistribuida_parcial"
    assert abs(pend.pct_ja_redistribuido - 0.05) < 1e-4


def test_redistribuir_pendencia_total(db, eap_basica):
    """Redistribuição total: 100% do saldo em duas parcelas."""
    _, folha = eap_basica
    ciclo = _abrir_bm_completo(db, folha.codigo, 20.0)
    svc.salvar_lancamentos(db, ciclo.id, [{"eap_codigo": folha.codigo, "pct_acumulado": 0.10}])
    _fechar_bm_completo(db, ciclo.id)

    pend = db.query(BmPendencia).filter(BmPendencia.ciclo_id == ciclo.id).first()

    svc.redistribuir_pendencia(db, pend.id, 2026, 6, 0.5, "planejador")
    svc.redistribuir_pendencia(db, pend.id, 2026, 7, 1.0, "planejador")
    db.refresh(pend)
    assert pend.status == "redistribuida_total"


def test_redistribuir_pendencia_atualiza_previsao(db, eap_basica):
    """Redistribuição deve atualizar EapPrevisaoMensal do mês destino."""
    _, folha = eap_basica
    ciclo = _abrir_bm_completo(db, folha.codigo, 20.0)
    svc.salvar_lancamentos(db, ciclo.id, [{"eap_codigo": folha.codigo, "pct_acumulado": 0.10}])
    _fechar_bm_completo(db, ciclo.id)

    pend = db.query(BmPendencia).filter(BmPendencia.ciclo_id == ciclo.id).first()
    svc.redistribuir_pendencia(db, pend.id, 2026, 6, 1.0, "planejador")

    prev_jun = (
        db.query(EapPrevisaoMensal)
        .filter(EapPrevisaoMensal.ano == 2026, EapPrevisaoMensal.mes == 6,
                EapPrevisaoMensal.eap_codigo == folha.codigo)
        .first()
    )
    assert prev_jun is not None
    assert abs(prev_jun.pct_previsto - 10.0) < 0.01  # gap 10% → 10% adicionado


def test_redistribuir_bloqueia_mes_fechado(db, eap_basica):
    """Redistribuição para mês com BM fechado deve ser bloqueada (Ponto 8)."""
    _, folha = eap_basica

    ciclo_mai = _abrir_bm_completo(db, folha.codigo, 20.0, mes=5)
    svc.salvar_lancamentos(db, ciclo_mai.id, [{"eap_codigo": folha.codigo, "pct_acumulado": 0.05}])
    _fechar_bm_completo(db, ciclo_mai.id)

    db.add(EapPrevisaoMensal(
        ano=2026, mes=6, eap_codigo=folha.codigo,
        pct_previsto=5.0, status_previsao="fechada",
    ))
    db.commit()
    ciclo_jun = svc.abrir_bm(db, 2026, 6)
    svc.salvar_lancamentos(db, ciclo_jun.id, [{"eap_codigo": folha.codigo, "pct_acumulado": 0.10}])
    _fechar_bm_completo(db, ciclo_jun.id)

    pend = db.query(BmPendencia).filter(BmPendencia.ciclo_id == ciclo_mai.id).first()
    assert pend is not None

    with pytest.raises(ValueError, match="BM.*fechado"):
        svc.redistribuir_pendencia(db, pend.id, 2026, 6, 1.0)


def test_redistribuir_bloqueia_previsao_convertida(db, eap_basica):
    """Redistribuição não pode alterar previsão já convertida (Ponto 7)."""
    _, folha = eap_basica

    # Fecha BM de maio com pendência
    ciclo_mai = _abrir_bm_completo(db, folha.codigo, 20.0, mes=5)
    svc.salvar_lancamentos(db, ciclo_mai.id, [{"eap_codigo": folha.codigo, "pct_acumulado": 0.10}])
    _fechar_bm_completo(db, ciclo_mai.id)

    # Abre BM de junho (marca previsão de junho como convertida)
    db.add(EapPrevisaoMensal(
        ano=2026, mes=6, eap_codigo=folha.codigo,
        pct_previsto=5.0, status_previsao="fechada",
    ))
    db.commit()
    svc.abrir_bm(db, 2026, 6)  # previsão de junho → convertida

    pend = db.query(BmPendencia).filter(BmPendencia.ciclo_id == ciclo_mai.id).first()

    # Redistribuir para junho deve falhar (previsão convertida)
    with pytest.raises(ValueError, match="convertida"):
        svc.redistribuir_pendencia(db, pend.id, 2026, 6, 1.0)


# ═══════════════════════════════════════════════════════════════════════════
# 7. SNAPSHOT IMUTÁVEL (Ponto 5)
# ═══════════════════════════════════════════════════════════════════════════

def test_snapshot_imutavel_apos_abertura(db, eap_basica):
    """Snapshot não pode ser alterado após criação do BM."""
    _, folha = eap_basica
    ciclo = _abrir_bm_completo(db, folha.codigo, 30.0)

    snap_original = db.query(BmSnapshotPrevisao).filter(
        BmSnapshotPrevisao.ciclo_id == ciclo.id
    ).first()
    pct_original = snap_original.pct_previsto

    # Alterar a previsão diretamente não deve afetar o snapshot
    prev = db.query(EapPrevisaoMensal).filter(
        EapPrevisaoMensal.ano == 2026, EapPrevisaoMensal.mes == 5
    ).first()
    prev.pct_previsto = 99.0  # tentativa de alterar após snapshot
    db.commit()

    db.refresh(snap_original)
    assert abs(snap_original.pct_previsto - pct_original) < 1e-4, \
        "Snapshot foi alterado — deveria ser imutável"


def test_reabrir_previsao_antes_de_abrir_bm(db, eap_basica):
    """Fechar e reabrir previsão antes de abrir o BM deve funcionar normalmente.

    Após reabrir: previsão volta para em_edicao e não há snapshots criados.
    """
    _, folha = eap_basica
    db.add(EapPrevisaoMensal(
        ano=2026, mes=5, eap_codigo=folha.codigo,
        pct_previsto=30.0, status_previsao="em_edicao",
    ))
    db.commit()

    svc.fechar_previsao_mensal(db, 2026, 5, "planejador")

    # Reabrir antes de abrir o BM — deve funcionar
    svc.reabrir_previsao_mensal(db, 2026, 5, "planejador")

    prev = db.query(EapPrevisaoMensal).filter(
        EapPrevisaoMensal.ano == 2026, EapPrevisaoMensal.mes == 5
    ).first()
    assert prev.status_previsao == "em_edicao"
    # Sem BM, não há snapshot
    assert db.query(BmSnapshotPrevisao).count() == 0


# ═══════════════════════════════════════════════════════════════════════════
# 8. DASHBOARD (Ponto 4)
# ═══════════════════════════════════════════════════════════════════════════

def test_dashboard_so_le_bm_fechado(db, eap_basica):
    """KPIs do dashboard devem ignorar BMs abertos (Ponto 4)."""
    _, folha = eap_basica

    ciclo = _abrir_bm_completo(db, folha.codigo, 50.0)
    svc.salvar_lancamentos(db, ciclo.id, [{"eap_codigo": folha.codigo, "pct_acumulado": 0.50}])

    kpis = svc.get_kpis_dashboard(db)
    assert kpis["ev"] == 0.0  # BM aberto não conta

    _fechar_bm_completo(db, ciclo.id)

    kpis_pos = svc.get_kpis_dashboard(db)
    assert kpis_pos["ev"] == 500_000.0  # 50% de 1M


# ═══════════════════════════════════════════════════════════════════════════
# 9. AUDITORIA (BmLog)
# ═══════════════════════════════════════════════════════════════════════════

def test_auditoria_registra_eventos(db, eap_basica):
    """BmLog deve registrar todos os eventos do ciclo de vida."""
    _, folha = eap_basica
    ciclo = _abrir_bm_completo(db, folha.codigo, 10.0)

    svc.salvar_lancamentos(db, ciclo.id, [{"eap_codigo": folha.codigo, "pct_acumulado": 0.10}])
    svc.transicionar_status(db, ciclo.id, svc.STATUS_EM_ANALISE, "analista")
    svc.transicionar_status(db, ciclo.id, svc.STATUS_PRE_APROVADA, "aprovador")
    svc.fechar_bm(db, ciclo.id, "gerente")
    svc.consolidar_bm(db, ciclo.id, "diretor")

    logs = db.query(BmLog).filter(BmLog.ciclo_id == ciclo.id).all()
    eventos = {l.evento for l in logs}

    assert "BM_ABERTO" in eventos
    assert "LANCAMENTO_SALVO" in eventos
    assert "STATUS_CHANGED" in eventos
    assert "BM_FECHADO" in eventos
    assert "BM_CONSOLIDADO" in eventos


# ═══════════════════════════════════════════════════════════════════════════
# 10. PREVISÃO (fechar, reabrir, convertida) — Ponto 7
# ═══════════════════════════════════════════════════════════════════════════

def test_previsao_fechar_reabrir(db, eap_basica):
    """fechar e reabrir previsão devem alterar status corretamente."""
    _, folha = eap_basica
    db.add(EapPrevisaoMensal(
        ano=2026, mes=5, eap_codigo=folha.codigo,
        pct_previsto=10.0, status_previsao="em_edicao",
    ))
    db.commit()

    resultado = svc.fechar_previsao_mensal(db, 2026, 5, "planejador")
    assert resultado["itens_fechados"] == 1

    prev = db.query(EapPrevisaoMensal).filter(
        EapPrevisaoMensal.ano == 2026, EapPrevisaoMensal.mes == 5
    ).first()
    assert prev.status_previsao == "fechada"

    resultado2 = svc.reabrir_previsao_mensal(db, 2026, 5, "planejador")
    assert resultado2["itens_reabertos"] == 1
    db.refresh(prev)
    assert prev.status_previsao == "em_edicao"


def test_previsao_convertida_nao_pode_voltar(db, eap_basica):
    """Previsão 'convertida' não pode ser reaberta (Ponto 7)."""
    _, folha = eap_basica
    db.add(EapPrevisaoMensal(
        ano=2026, mes=5, eap_codigo=folha.codigo,
        pct_previsto=10.0, status_previsao="convertida",
    ))
    db.commit()

    with pytest.raises(ValueError, match="convertida"):
        svc.reabrir_previsao_mensal(db, 2026, 5, "planejador")


def test_previsao_nao_pode_fechar_bm_ja_fechado(db, eap_basica):
    """Não deve fechar previsão de mês cujo BM já está fechado."""
    _, folha = eap_basica
    ciclo = _abrir_bm_completo(db, folha.codigo, 10.0)
    _fechar_bm_completo(db, ciclo.id)

    with pytest.raises(ValueError, match="já está fechado|já está"):
        svc.fechar_previsao_mensal(db, 2026, 5, "planejador")


# ═══════════════════════════════════════════════════════════════════════════
# 11. VALIDAÇÃO FINANCEIRA DE PERCENTUAIS (Ponto 11 — nova camada)
# ═══════════════════════════════════════════════════════════════════════════

from backend.utils.validators import normalize_pct, normalize_pct_100, check_acumulado_teto


class TestNormalizePct:
    """normalize_pct — escala interna 0.0–1.0."""

    def test_valor_zero(self):
        assert normalize_pct(0.0) == 0.0

    def test_valor_um(self):
        assert normalize_pct(1.0) == 1.0

    def test_valor_meio(self):
        assert normalize_pct(0.5) == 0.5

    def test_negativo_lanca(self):
        with pytest.raises(ValueError, match="negativo"):
            normalize_pct(-0.01)

    def test_negativo_grande_lanca(self):
        with pytest.raises(ValueError, match="negativo"):
            normalize_pct(-100.0)

    def test_acima_de_um_lanca(self):
        with pytest.raises(ValueError, match="excede 100"):
            normalize_pct(1.001)

    def test_acima_de_um_grande_lanca(self):
        with pytest.raises(ValueError, match="excede 100"):
            normalize_pct(1.5)

    def test_nan_lanca(self):
        import math
        with pytest.raises(ValueError, match="finito"):
            normalize_pct(math.nan)

    def test_inf_lanca(self):
        import math
        with pytest.raises(ValueError, match="finito"):
            normalize_pct(math.inf)

    def test_none_lanca(self):
        with pytest.raises(ValueError, match="nulo"):
            normalize_pct(None)

    def test_string_percentual(self):
        assert normalize_pct("0.75%") == 0.75

    def test_string_invalida_lanca(self):
        with pytest.raises(ValueError, match="numérico"):
            normalize_pct("abc")

    def test_string_vazia_lanca(self):
        with pytest.raises(ValueError, match="vazia"):
            normalize_pct("")

    def test_codigo_aparece_na_mensagem(self):
        with pytest.raises(ValueError, match="1\\.1\\.1"):
            normalize_pct(-0.5, codigo="1.1.1")


class TestNormalizePct100:
    """normalize_pct_100 — escala legada 0–100 (eap_previsao_mensal)."""

    def test_valor_zero(self):
        assert normalize_pct_100(0.0) == 0.0

    def test_valor_cem(self):
        assert normalize_pct_100(100.0) == 100.0

    def test_valor_tipico(self):
        assert normalize_pct_100(75.5) == 75.5

    def test_negativo_lanca(self):
        with pytest.raises(ValueError, match="negativo"):
            normalize_pct_100(-1.0)

    def test_acima_100_lanca(self):
        with pytest.raises(ValueError, match="excede 100"):
            normalize_pct_100(100.001)

    def test_150_lanca(self):
        with pytest.raises(ValueError, match="excede 100"):
            normalize_pct_100(150.0)

    def test_string_com_simbolo(self):
        assert normalize_pct_100("75.5%") == 75.5

    def test_none_lanca(self):
        with pytest.raises(ValueError, match="nulo"):
            normalize_pct_100(None)


class TestCheckAcumuladoTeto:
    """check_acumulado_teto — defesa contra overflow de acumulado."""

    def test_cem_porcento_ok(self):
        check_acumulado_teto(1.0)  # não lança

    def test_zero_ok(self):
        check_acumulado_teto(0.0)  # não lança

    def test_parcial_ok(self):
        check_acumulado_teto(0.75)  # não lança

    def test_acima_do_teto_lanca(self):
        with pytest.raises(ValueError, match="excede 100%"):
            check_acumulado_teto(1.0001)

    def test_codigo_na_mensagem(self):
        with pytest.raises(ValueError, match="1\\.2\\.3"):
            check_acumulado_teto(1.5, codigo="1.2.3")


def test_lancamento_negativo_rejeitado(db, eap_basica):
    """Service deve rejeitar pct_acumulado negativo nos lançamentos."""
    _, folha = eap_basica
    ciclo = _abrir_bm_completo(db, folha.codigo, 30.0)

    with pytest.raises(ValueError, match="negativo|0% até 100%"):
        svc.salvar_lancamentos(
            db, ciclo.id,
            [{"eap_codigo": folha.codigo, "pct_acumulado": -0.1}],
        )


def test_lancamento_acima_100_rejeitado(db, eap_basica):
    """Service deve rejeitar pct_acumulado > 1.0 nos lançamentos."""
    _, folha = eap_basica
    ciclo = _abrir_bm_completo(db, folha.codigo, 30.0)

    with pytest.raises(ValueError, match="excede 100%|0% até 100%"):
        svc.salvar_lancamentos(
            db, ciclo.id,
            [{"eap_codigo": folha.codigo, "pct_acumulado": 1.5}],
        )


def test_lancamento_nan_rejeitado(db, eap_basica):
    """Service deve rejeitar NaN nos lançamentos."""
    import math
    _, folha = eap_basica
    ciclo = _abrir_bm_completo(db, folha.codigo, 30.0)

    with pytest.raises(ValueError, match="finito|0% até 100%"):
        svc.salvar_lancamentos(
            db, ciclo.id,
            [{"eap_codigo": folha.codigo, "pct_acumulado": math.nan}],
        )


def test_redistribuir_pct_zero_rejeitado(db, eap_basica):
    """Redistribuição com pct_redistribuir=0 deve ser rejeitada."""
    _, folha = eap_basica
    ciclo = _abrir_bm_completo(db, folha.codigo, 30.0)
    svc.salvar_lancamentos(db, ciclo.id, [{"eap_codigo": folha.codigo, "pct_acumulado": 0.0}])
    _fechar_bm_completo(db, ciclo.id)

    pend = db.query(svc.BmPendencia).filter(svc.BmPendencia.ciclo_id == ciclo.id).first()
    if pend is None:
        pytest.skip("Nenhuma pendência gerada (gap=0)")

    with pytest.raises(ValueError, match="0|positivo|maior que 0"):
        svc.redistribuir_pendencia(db, pend.id, 2026, 6, 0.0)


def test_redistribuir_pct_acima_100_rejeitado(db, eap_basica):
    """Redistribuição com pct_redistribuir > 1.0 deve ser rejeitada."""
    _, folha = eap_basica
    ciclo = _abrir_bm_completo(db, folha.codigo, 50.0)
    svc.salvar_lancamentos(db, ciclo.id, [{"eap_codigo": folha.codigo, "pct_acumulado": 0.0}])
    _fechar_bm_completo(db, ciclo.id)

    pend = db.query(svc.BmPendencia).filter(svc.BmPendencia.ciclo_id == ciclo.id).first()
    if pend is None:
        pytest.skip("Nenhuma pendência gerada (gap=0)")

    with pytest.raises(ValueError, match="excede 100%|0% até 100%"):
        svc.redistribuir_pendencia(db, pend.id, 2026, 6, 1.5)


# ═══════════════════════════════════════════════════════════════════════════
# 12. PROPAGAÇÃO DO PREVISTO NA HIERARQUIA
# ═══════════════════════════════════════════════════════════════════════════

def test_previsto_propagado_para_pai(db, eap_dois_filhos):
    """Pai deve exibir pct_previsto > 0 quando filhos têm previsão.

    Problema original: snaps.get(pai, 0.0) retornava 0 porque snapshots
    só têm folhas. Após a correção, _propagar_previsto() calcula o pai como
    média ponderada dos filhos.
    """
    pai, f1, f2 = eap_dois_filhos

    # Cria previsões para ambas as folhas
    db.add_all([
        EapPrevisaoMensal(ano=2026, mes=5, eap_codigo=f1.codigo,
                          pct_previsto=40.0, status_previsao="fechada"),
        EapPrevisaoMensal(ano=2026, mes=5, eap_codigo=f2.codigo,
                          pct_previsto=20.0, status_previsao="fechada"),
    ])
    db.commit()

    ciclo = svc.abrir_bm(db, 2026, 5, "planejador")
    bm = svc.montar_bm_completo(db, ciclo.id)

    itens = {i["codigo"]: i for i in bm["itens"]}

    # Folhas devem ter pct_previsto correto (do snapshot)
    assert abs(itens[f1.codigo]["pct_previsto"] - 0.40) < 1e-4
    assert abs(itens[f2.codigo]["pct_previsto"] - 0.20) < 1e-4

    # Pai deve ter pct_previsto propagado: (600k*0.40 + 400k*0.20) / 1000k = 0.32
    pct_pai_esperado = (600_000.0 * 0.40 + 400_000.0 * 0.20) / 1_000_000.0
    assert abs(itens[pai.codigo]["pct_previsto"] - pct_pai_esperado) < 1e-4, \
        f"pct_previsto do pai={itens[pai.codigo]['pct_previsto']:.4f}, esperado={pct_pai_esperado:.4f}"


def test_valor_previsto_pai_correto(db, eap_dois_filhos):
    """valor_previsto do pai deve ser a soma ponderada dos filhos."""
    pai, f1, f2 = eap_dois_filhos
    db.add_all([
        EapPrevisaoMensal(ano=2026, mes=5, eap_codigo=f1.codigo,
                          pct_previsto=50.0, status_previsao="fechada"),
        EapPrevisaoMensal(ano=2026, mes=5, eap_codigo=f2.codigo,
                          pct_previsto=50.0, status_previsao="fechada"),
    ])
    db.commit()
    ciclo = svc.abrir_bm(db, 2026, 5, "planejador")
    bm = svc.montar_bm_completo(db, ciclo.id)
    itens = {i["codigo"]: i for i in bm["itens"]}

    # 50% de 600k = 300k; 50% de 400k = 200k; pai = 500k
    assert abs(itens[f1.codigo]["valor_previsto"] - 300_000.0) < 1.0
    assert abs(itens[f2.codigo]["valor_previsto"] - 200_000.0) < 1.0
    assert abs(itens[pai.codigo]["valor_previsto"] - 500_000.0) < 1.0


def test_total_previsto_soma_nivel1(db, eap_dois_filhos):
    """total_valor_previsto deve somar apenas nível 1 (sem dupla contagem)."""
    pai, f1, f2 = eap_dois_filhos
    db.add_all([
        EapPrevisaoMensal(ano=2026, mes=5, eap_codigo=f1.codigo,
                          pct_previsto=30.0, status_previsao="fechada"),
        EapPrevisaoMensal(ano=2026, mes=5, eap_codigo=f2.codigo,
                          pct_previsto=50.0, status_previsao="fechada"),
    ])
    db.commit()
    ciclo = svc.abrir_bm(db, 2026, 5, "planejador")
    bm = svc.montar_bm_completo(db, ciclo.id)

    # 30% de 600k = 180k; 50% de 400k = 200k; total = 380k
    esperado = 600_000.0 * 0.30 + 400_000.0 * 0.50
    assert abs(bm["total_valor_previsto"] - esperado) < 1.0
    assert abs(bm["total_pct_previsto"] - esperado / 1_000_000.0) < 1e-4


def test_desvio_periodo_correto(db, eap_basica):
    """desvio_valor_periodo = medido - previsto; negativo = abaixo do previsto."""
    _, folha = eap_basica
    ciclo = _abrir_bm_completo(db, folha.codigo, 50.0)  # previsto 50%
    svc.salvar_lancamentos(db, ciclo.id, [{"eap_codigo": folha.codigo, "pct_acumulado": 0.30}])
    bm = svc.montar_bm_completo(db, ciclo.id)

    # medido: 30% de 1M = 300k; previsto: 50% de 1M = 500k; desvio = -200k
    assert abs(bm["desvio_valor_periodo"] - (-200_000.0)) < 1.0
    assert abs(bm["desvio_pct_periodo"] - (-0.20)) < 1e-4


def test_desvio_positivo_quando_adiantado(db, eap_basica):
    """desvio positivo quando medido > previsto."""
    _, folha = eap_basica
    ciclo = _abrir_bm_completo(db, folha.codigo, 30.0)  # previsto 30%
    svc.salvar_lancamentos(db, ciclo.id, [{"eap_codigo": folha.codigo, "pct_acumulado": 0.60}])
    bm = svc.montar_bm_completo(db, ciclo.id)

    # medido: 60% de 1M = 600k; previsto: 30% de 1M = 300k; desvio = +300k
    assert bm["desvio_valor_periodo"] > 0
    assert abs(bm["desvio_valor_periodo"] - 300_000.0) < 1.0


def test_previsto_propagado_apos_fechamento(db, eap_dois_filhos):
    """Após fechar BM, _montar_de_consolidado também propaga previsto corretamente."""
    pai, f1, f2 = eap_dois_filhos
    db.add_all([
        EapPrevisaoMensal(ano=2026, mes=5, eap_codigo=f1.codigo,
                          pct_previsto=60.0, status_previsao="fechada"),
        EapPrevisaoMensal(ano=2026, mes=5, eap_codigo=f2.codigo,
                          pct_previsto=40.0, status_previsao="fechada"),
    ])
    db.commit()
    ciclo = svc.abrir_bm(db, 2026, 5, "planejador")
    svc.salvar_lancamentos(db, ciclo.id, [
        {"eap_codigo": f1.codigo, "pct_acumulado": 0.60},
        {"eap_codigo": f2.codigo, "pct_acumulado": 0.40},
    ])
    _fechar_bm_completo(db, ciclo.id)

    bm = svc.montar_bm_completo(db, ciclo.id)
    itens = {i["codigo"]: i for i in bm["itens"]}

    # Pai propagado: (600k*0.60 + 400k*0.40) / 1000k = 0.52
    pct_pai = (600_000 * 0.60 + 400_000 * 0.40) / 1_000_000
    assert abs(itens[pai.codigo]["pct_previsto"] - pct_pai) < 1e-4


# ═══════════════════════════════════════════════════════════════════════════
# 13. KPIS DASHBOARD — COMPETÊNCIA DE REFERÊNCIA
# ═══════════════════════════════════════════════════════════════════════════

def test_kpis_usam_competencia_referencia_nao_ultimo_ponto(db, eap_basica):
    """get_kpis_dashboard NÃO deve usar pontos[-1] (fim do projeto).

    Cenário: BM fechado em mai/2026 com 50% de EV.
    A curva planejada pode continuar até dez/2027 (pv_acum=100%).
    O dashboard deve mostrar PV e EV até mai/2026, não até dez/2027.
    """
    _, folha = eap_basica
    ciclo = _abrir_bm_completo(db, folha.codigo, 50.0)
    svc.salvar_lancamentos(db, ciclo.id, [{"eap_codigo": folha.codigo, "pct_acumulado": 0.50}])
    _fechar_bm_completo(db, ciclo.id)

    kpis = svc.get_kpis_dashboard(db)

    # competencia_referencia deve ser 2026/05 (o BM fechado)
    assert kpis["competencia_referencia"] == "2026/05"

    # EV deve ser 50% de 1M = 500k (correto)
    assert abs(kpis["ev"] - 500_000.0) < 1.0


def test_helper_competencia_referencia_sem_bm(db):
    """Sem nenhum BM fechado, retorna mês atual (não erro)."""
    from datetime import date
    ano, mes = svc._get_competencia_referencia(db)
    today = date.today()
    assert ano == today.year
    assert mes == today.month


def test_helper_ponto_curva_exato(db):
    """_get_ponto_curva_por_competencia retorna ponto exato quando existe."""
    pontos = [
        {"data": "2026-03-01", "pv_acum": 100_000.0, "ev_acum": 90_000.0},
        {"data": "2026-04-01", "pv_acum": 200_000.0, "ev_acum": 180_000.0},
        {"data": "2026-05-01", "pv_acum": 350_000.0, "ev_acum": 300_000.0},
    ]
    p = svc._get_ponto_curva_por_competencia(pontos, 2026, 4)
    assert p["pv_acum"] == 200_000.0


def test_helper_ponto_curva_anterior_quando_sem_exato(db):
    """_get_ponto_curva_por_competencia usa último ponto anterior quando não há exato."""
    pontos = [
        {"data": "2026-03-01", "pv_acum": 100_000.0, "ev_acum": 90_000.0},
        {"data": "2026-05-01", "pv_acum": 350_000.0, "ev_acum": 300_000.0},
    ]
    # Competência abr/2026 não existe — deve usar mar/2026
    p = svc._get_ponto_curva_por_competencia(pontos, 2026, 4)
    assert p["pv_acum"] == 100_000.0


def test_kpis_campos_legados_mantidos(db, eap_basica):
    """Campos legados (pv, ev, spi, pct_pv, pct_ev) devem estar presentes."""
    _, folha = eap_basica
    ciclo = _abrir_bm_completo(db, folha.codigo, 30.0)
    svc.salvar_lancamentos(db, ciclo.id, [{"eap_codigo": folha.codigo, "pct_acumulado": 0.30}])
    _fechar_bm_completo(db, ciclo.id)

    kpis = svc.get_kpis_dashboard(db)

    # Campos legados devem existir
    for campo in ["pv", "ev", "spi", "pct_pv", "pct_ev", "bac", "vac", "cv_pct"]:
        assert campo in kpis, f"Campo legado '{campo}' ausente nos KPIs"

    # Campos novos também devem existir
    for campo in ["competencia_referencia", "pv_acum_referencia", "ev_acum_referencia",
                  "pct_pv_referencia", "pct_ev_referencia", "spi_referencia"]:
        assert campo in kpis, f"Campo novo '{campo}' ausente nos KPIs"
