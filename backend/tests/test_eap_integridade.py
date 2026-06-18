"""Testes de integridade hierárquica da EAP — síntese + gate + propagação.

Cobre o Achado A:
  - pai intermediário ausente (simples);
  - pai E avô intermediários ausentes (recursivo);
  - propagação com pai de valor 0;
  - folha alcançando o nível 1 em 100% da EAP após a síntese.
"""
import pytest

from backend.models import EapItem
from backend.services.eap_integrity import (
    sintetizar_intermediarios, checar_integridade, DESC_SINTETIZADO, parent_de,
)
from backend.services.bm_service import _propagar_bottom_up, _carregar_eap


# ── Helpers ───────────────────────────────────────────────────────────────────

def _item(codigo, valor=0.0, descricao="x"):
    return {
        "codigo": codigo,
        "descricao": descricao,
        "nivel": len(codigo.split(".")),
        "parent_codigo": parent_de(codigo),
        "valor": valor,
        "dist_mensal": {},
    }


def _por_codigo(itens):
    return {it["codigo"]: it for it in itens}


# ═══════════════════════════════════════════════════════════════════════════
# 1. Pai intermediário ausente — caso simples (1.3.4 ausente)
# ═══════════════════════════════════════════════════════════════════════════

def test_sintese_pai_intermediario_simples():
    """Existe 1, 1.3, 1.3.4.12 e folha 1.3.4.12.1 — falta 1.3.4 (nível 3)."""
    itens = [
        _item("1", 1000.0),
        _item("1.3", 1000.0),
        _item("1.3.4.12", 0.0),          # pai do item órfão (nível 4)
        _item("1.3.4.12.1", 800.0),      # folha
    ]
    # Antes: integridade quebrada (1.3.4 ausente)
    antes = checar_integridade(itens)
    assert not antes["ok"]
    assert "1.3.4" in antes["orfaos"]

    completos, sint = sintetizar_intermediarios(itens)
    by = _por_codigo(completos)

    # 1.3.4 foi criado
    assert "1.3.4" in by
    assert by["1.3.4"]["descricao"] == DESC_SINTETIZADO
    assert by["1.3.4"]["nivel"] == 3
    assert by["1.3.4"]["parent_codigo"] == "1.3"
    # valor sintetizado = soma dos filhos diretos (1.3.4.12)
    assert by["1.3.4"]["valor"] == pytest.approx(by["1.3.4.12"]["valor"])

    # Depois: íntegro
    assert checar_integridade(completos)["ok"]
    assert [s["codigo"] for s in sint] == ["1.3.4"]


# ═══════════════════════════════════════════════════════════════════════════
# 2. Pai E avô ausentes — síntese recursiva (5.3 e 5.3.9 ausentes)
# ═══════════════════════════════════════════════════════════════════════════

def test_sintese_recursiva_pai_e_avo_ausentes():
    """Existe 5 e a folha 5.3.9.1.1 — faltam 5.3 (nível 2) e 5.3.9 (nível 3)
    e 5.3.9.1 (nível 4). Tudo deve ser sintetizado recursivamente."""
    itens = [
        _item("5", 5000.0),
        _item("5.3.9.1.1", 1500.0),   # folha profunda; faltam 5.3, 5.3.9, 5.3.9.1
    ]
    completos, sint = sintetizar_intermediarios(itens)
    by = _por_codigo(completos)

    for cod in ("5.3", "5.3.9", "5.3.9.1"):
        assert cod in by, f"intermediário {cod} não sintetizado"
        assert by[cod]["descricao"] == DESC_SINTETIZADO

    # Cadeia completa e valores telescópicos: cada intermediário = soma dos filhos
    assert by["5.3.9.1"]["valor"] == pytest.approx(1500.0)
    assert by["5.3.9"]["valor"] == pytest.approx(1500.0)
    assert by["5.3"]["valor"] == pytest.approx(1500.0)

    integ = checar_integridade(completos)
    assert integ["ok"], integ
    assert {"5.3", "5.3.9", "5.3.9.1"}.issubset({s["codigo"] for s in sint})


# ═══════════════════════════════════════════════════════════════════════════
# 3. Propagação bottom-up com pai de valor 0
# ═══════════════════════════════════════════════════════════════════════════

def test_propagar_bottom_up_pai_valor_zero():
    """Pai com valor=0 NÃO deve interromper a propagação do % para o avô."""
    todos = [
        EapItem(codigo="1",     descricao="raiz", nivel=1, valor=1000.0),
        EapItem(codigo="1.1",   descricao="meio", nivel=2, parent_codigo="1", valor=0.0),  # valor 0!
        EapItem(codigo="1.1.1", descricao="folha", nivel=3, parent_codigo="1.1", valor=1000.0),
    ]
    folhas = {"1.1.1"}
    pct = _propagar_bottom_up(todos, folhas, {"1.1.1": 0.40})

    # Pai de valor 0 cai para a soma do valor dos filhos como denominador
    assert pct["1.1"] == pytest.approx(0.40), pct
    # E o nível 1 recebe a propagação (não fica 0)
    assert pct["1"] == pytest.approx(0.40), pct


def test_propagar_bottom_up_valor_positivo_inalterado():
    """Comportamento com valor>0 permanece idêntico (ponderação financeira)."""
    todos = [
        EapItem(codigo="1",   descricao="raiz", nivel=1, valor=1000.0),
        EapItem(codigo="1.1", descricao="a", nivel=2, parent_codigo="1", valor=600.0),
        EapItem(codigo="1.2", descricao="b", nivel=2, parent_codigo="1", valor=400.0),
    ]
    folhas = {"1.1", "1.2"}
    pct = _propagar_bottom_up(todos, folhas, {"1.1": 0.50, "1.2": 0.25})
    # (600*0.5 + 400*0.25) / 1000 = 0.40
    assert pct["1"] == pytest.approx(0.40)


# ═══════════════════════════════════════════════════════════════════════════
# 4. Após síntese, 100% das folhas alcançam o nível 1 (cenário real reduzido)
# ═══════════════════════════════════════════════════════════════════════════

def test_todas_folhas_alcancam_nivel1_apos_sintese():
    """Reproduz os padrões reais da EAP: vários ramos com intermediário ausente.
    Após a síntese, NENHUM item pode ficar sem cadeia até o nível 1."""
    itens = [
        _item("1", 0.0),
        _item("1.3", 0.0),
        _item("1.3.1", 0.0),
        _item("1.3.1.5.9", 8059.59),       # 1.3.1.5 ausente
        _item("1.3.4.12.10", 8059.59),     # 1.3.4 ausente
        _item("4", 0.0),
        _item("4.2.2.7.1", 193066.27),     # 4.2, 4.2.2, 4.2.2.7 ausentes
        _item("5", 0.0),
        _item("5.3.9.1", 202426.85),       # 5.3, 5.3.9 ausentes
    ]
    completos, sint = sintetizar_intermediarios(itens)
    integ = checar_integridade(completos)
    assert integ["ok"], integ
    assert integ["quebrados"] == []
    assert integ["orfaos"] == []
    # Os intermediários esperados foram criados
    esperados = {"1.3.1.5", "1.3.4", "4.2", "4.2.2", "4.2.2.7", "5.3", "5.3.9"}
    assert esperados.issubset({s["codigo"] for s in sint})


def test_gate_detecta_quebra_quando_nao_sintetizado():
    """O gate (checar_integridade) deve reprovar uma EAP com órfão não tratado."""
    itens = [_item("1", 100.0), _item("1.2.3", 50.0)]  # 1.2 ausente
    integ = checar_integridade(itens)
    assert not integ["ok"]
    assert "1.2" in integ["orfaos"]
    assert "1.2.3" in integ["quebrados"]


def test_eap_ja_integra_nao_sintetiza_nada():
    """EAP sem buracos não deve gerar nós sintéticos."""
    itens = [_item("1", 100.0), _item("1.1", 60.0), _item("1.2", 40.0)]
    completos, sint = sintetizar_intermediarios(itens)
    assert sint == []
    assert len(completos) == 3
    assert checar_integridade(completos)["ok"]
