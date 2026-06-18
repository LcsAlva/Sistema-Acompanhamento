"""Serviço de Boletim de Medição (BM) — lógica de negócio isolada.

════════════════════════════════════════════════════════════════════════════════
FONTE ÚNICA DE VERDADE (Ponto 4)
════════════════════════════════════════════════════════════════════════════════
  BmCiclo     → fonte oficial de todos os ciclos de medição
  BmConsolidado → fonte oficial dos acumulados financeiros (gravado ao fechar)
  CicloMedicao  → LEGADO. Mantido apenas para compatibilidade com PDF e outros
                  módulos antigos. NÃO deve ser lido para lógica de BM novo.

Espelhamento é UNIDIRECIONAL: novo BM → legado. NUNCA o contrário.
Código legado (eap.py, CicloMedicao) NÃO deve sobrescrever dados do BM novo.

════════════════════════════════════════════════════════════════════════════════
MÁQUINAS DE ESTADO
════════════════════════════════════════════════════════════════════════════════
  BM:        em_previa → em_analise → pre_aprovada → fechada → consolidada
  Previsão:  em_edicao → fechada → convertida

  Quem pode editar:
    - em_previa / em_analise / pre_aprovada : lançamentos permitidos
    - fechada / consolidada               : IMUTÁVEL, sem exceções

  O que gera snapshot:    abrir_bm()          (previsão → BmSnapshotPrevisao)
  O que gera consolidado: fechar_bm()         (lançamentos → BmConsolidado)
  O que gera pendência:   fechar_bm()         (consolidado vs snapshot)
  O que é imutável:       snapshot, consolidado, pendências após fechamento

════════════════════════════════════════════════════════════════════════════════
ATOMICIDADE (Ponto 6)
════════════════════════════════════════════════════════════════════════════════
  fechar_bm() executa todas as etapas com um único db.commit() ao final.
  Se qualquer etapa lançar exceção: o get_db() garante rollback automático.
  Nunca há commit parcial dentro do fluxo de fechamento.

════════════════════════════════════════════════════════════════════════════════
ESCALA INTERNA
════════════════════════════════════════════════════════════════════════════════
  0.0–1.0 para todos os % neste módulo.
  EapPrevisaoMensal.pct_previsto usa 0-100 (legado) — converter ao ler.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from ..utils.validators import normalize_pct, check_acumulado_teto
from .competencia_service import assert_competencia_editavel, get_or_create_competencia
from ..models import (
    EapItem,
    EapPrevisaoMensal,
    BmCiclo,
    BmSnapshotPrevisao,
    BmLancamento,
    BmVersao,
    BmConsolidado,
    BmPendencia,
    BmPendenciaRedistrib,
    BmLog,
    CicloMedicao,
    LancamentoMedicao,
)

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Baseline visual da EAP ET-5275.00-2000-911-E6G-002=J.
# Fonte: aba "Curva Financeira" da EAP J, linhas 118/119.
# Os valores sao percentuais acumulados do contrato; o PV mensal e a diferenca
# entre meses consecutivos.
PV_LB_ACUM_EAP_J: dict[str, float] = {
    "2025-08-01": 0.4499999998264354,
    "2025-09-01": 1.210925925458873,
    "2025-10-01": 2.1057275799600843,
    "2025-11-01": 3.079642671572453,
    "2025-12-01": 3.7891304070538574,
    "2026-01-01": 4.939650064255602,
    "2026-02-01": 5.694648990690094,
    "2026-03-01": 8.239329032312611,
    "2026-04-01": 11.402237690915799,
    "2026-05-01": 15.084671450054406,
    "2026-06-01": 18.84960995349211,
    "2026-07-01": 24.490175837938814,
    "2026-08-01": 31.373352868878573,
    "2026-09-01": 41.52592829467359,
    "2026-10-01": 48.973815435598524,
    "2026-11-01": 54.261102984884545,
    "2026-12-01": 57.99873664998254,
    "2027-01-01": 59.71745090563013,
    "2027-02-01": 68.6804175997674,
    "2027-03-01": 76.00889871461432,
    "2027-04-01": 80.79126862454959,
    "2027-05-01": 88.45164241320558,
    "2027-06-01": 94.39145770834271,
    "2027-07-01": 96.464638703041,
    "2027-08-01": 97.17629608938876,
    "2027-09-01": 98.25954649357054,
    "2027-10-01": 99.21214814840468,
    "2027-11-01": 99.57603703720055,
    "2027-12-01": 99.99999999999999,
    "2028-01-01": 99.99999999999999,
    "2028-02-01": 99.99999999999999,
}


PV_FASE_MENSAL_EAP_J: dict[str, dict[str, float]] = {
    "1": {
        "2025-08-01": 11.249999999999998, "2025-09-01": 19.02314814814815, "2025-10-01": 22.37004137115839,
        "2025-11-01": 7.857647754137115, "2025-12-01": 0.3126477541371158, "2026-01-01": 0.3126477541371158,
        "2026-02-01": 0.2900413711583924, "2026-03-01": 0.3126477541371158, "2026-04-01": 0.3126477541371158,
        "2026-05-01": 0.3126477541371158, "2026-06-01": 0.2900413711583924, "2026-07-01": 0.3126477541371158,
        "2026-08-01": 0.3126477541371158, "2026-09-01": 0.3126477541371158, "2026-10-01": 0.3126477541371158,
        "2026-11-01": 0.3126477541371158, "2026-12-01": 0.2900413711583924, "2027-01-01": 0.3126477541371158,
        "2027-02-01": 0.3126477541371158, "2027-03-01": 0.3126477541371158, "2027-04-01": 0.2900413711583924,
        "2027-05-01": 0.3126477541371158, "2027-06-01": 0.3126477541371158, "2027-07-01": 0.3126477541371158,
        "2027-08-01": 0.3126477541371158, "2027-09-01": 11.412647754137112, "2027-10-01": 4.490041371158392,
        "2027-11-01": 6.522222222222221, "2027-12-01": 10.599074074074071,
    },
    "2": {
        "2025-11-01": 10.99348636034074, "2025-12-01": 2.953541981439982, "2026-01-01": 6.156569585923092,
        "2026-02-01": 4.786211835866907, "2026-03-01": 4.7418896848563925, "2026-04-01": 6.626535997159404,
        "2026-05-01": 4.398730996577019, "2026-06-01": 3.5814290395781536, "2026-07-01": 18.790359304246902,
        "2026-08-01": 16.018354147936424, "2026-09-01": 6.6671767807983855, "2026-10-01": 0.23809523808794394,
        "2026-11-01": 0.3571428571319159, "2026-12-01": 0.3571428571319159, "2027-01-01": 0.9126984126704518,
        "2027-02-01": 1.4682539682089875, "2027-03-01": 1.4682539682089875, "2027-04-01": 1.4682539682089875,
        "2027-05-01": 1.3492063491650157, "2027-06-01": 1.3492063491650157, "2027-07-01": 0.5555555555385359,
        "2027-08-01": 2.8571428570553272, "2027-09-01": 1.9047619047035516,
    },
    "3": {
        "2025-12-01": 10.395386131066742, "2026-01-01": 13.772391440962364, "2026-02-01": 2.406921433862205,
        "2026-03-01": 2.983488690214546, "2026-04-01": 8.203747049811765, "2026-05-01": 6.793508362286668,
        "2026-06-01": 6.583979496395298, "2026-07-01": 7.156182101277706, "2026-08-01": 12.087745388548338,
        "2026-09-01": 10.239496724358231, "2026-10-01": 8.430115801631683, "2026-11-01": 8.476462140639953,
        "2026-12-01": 2.339570549031247, "2027-01-01": 0.13100468991325356,
    },
    "4": {
        "2026-03-01": 0.09437674015558555, "2026-04-01": 0.4718837007779278, "2026-05-01": 0.8136032444263714,
        "2026-06-01": 2.7840318581080417, "2026-07-01": 4.490395467264116, "2026-08-01": 4.639700288485688,
        "2026-09-01": 9.306450459441157, "2026-10-01": 6.314309378182806, "2026-11-01": 7.800780966225859,
        "2026-12-01": 4.301539431459375, "2027-01-01": 2.9703868227841475, "2027-02-01": 2.9098606136468756,
        "2027-03-01": 7.533433958311172, "2027-04-01": 9.903528423875017, "2027-05-01": 18.192157174304256,
        "2027-06-01": 13.448383412975684, "2027-07-01": 3.7986034157882687, "2027-08-01": 0.17996456778182848,
        "2027-09-01": 0.04661007600581567,
    },
    "5": {
        "2026-01-01": 1.0, "2026-02-01": 0.7499999999999999, "2026-03-01": 4.402564102564103,
        "2026-04-01": 5.498717948717948, "2026-05-01": 4.748717948717949, "2026-06-01": 4.748717948717949,
        "2026-07-01": 4.748717948717949, "2026-08-01": 4.963003663003663, "2026-09-01": 4.963003663003663,
        "2026-10-01": 4.963003663003663, "2026-11-01": 4.963003663003663, "2026-12-01": 4.963003663003663,
        "2027-01-01": 4.963003663003663, "2027-02-01": 4.963003663003663, "2027-03-01": 4.963003663003663,
        "2027-04-01": 2.1937728937728935, "2027-05-01": 0.3476190476190476, "2027-06-01": 3.414285714285714,
        "2027-07-01": 5.664285714285714, "2027-08-01": 5.664285714285714, "2027-09-01": 6.164285714285713,
        "2027-10-01": 9.662499999999998, "2027-11-01": 1.2874999999999996,
    },
    "6": {
        "2026-02-01": 0.7758443816978755, "2026-03-01": 4.801020481504697, "2026-04-01": 4.801020481504697,
        "2026-05-01": 6.606754368956381, "2026-06-01": 4.712264206106107, "2026-07-01": 5.3490579933906055,
        "2026-08-01": 8.395690387463835, "2026-09-01": 13.989037572142815, "2026-10-01": 11.209150447789895,
        "2026-11-01": 3.3739563112582838, "2026-12-01": 3.959565491731428, "2027-01-01": 0.047478241641221754,
        "2027-02-01": 20.41547985792443, "2027-03-01": 10.430339137974665, "2027-04-01": 1.1333406389130543,
    },
}


def _pv_lb_eap_j(bac: float) -> tuple[dict[str, float], dict[str, float]]:
    pv_acum_por_mes: dict[str, float] = {}
    pv_por_mes: dict[str, float] = {}
    acumulado_anterior = 0.0
    for iso, pct_acum in sorted(PV_LB_ACUM_EAP_J.items()):
        acumulado = bac * (pct_acum / 100.0)
        pv_acum_por_mes[iso] = acumulado
        pv_por_mes[iso] = max(0.0, acumulado - acumulado_anterior)
        acumulado_anterior = acumulado
    return pv_por_mes, pv_acum_por_mes


def previsto_fase_lb_eap_j(codigo_fase: str, ano: int, mes: int, valor_fase: float) -> dict[str, float] | None:
    """Previsto por fase da EAP J, em escala 0.0-1.0 sobre o valor da fase."""
    serie = PV_FASE_MENSAL_EAP_J.get(str(codigo_fase))
    if not serie:
        return None

    iso = f"{ano:04d}-{mes:02d}-01"
    pct_periodo = float(serie.get(iso, 0.0)) / 100.0
    pct_acum = sum(float(v) for k, v in serie.items() if k <= iso) / 100.0
    pct_acum = min(max(pct_acum, 0.0), 1.0)
    valor = float(valor_fase or 0.0)

    return {
        "pct_previsto_periodo": pct_periodo,
        "pct_previsto_acum": pct_acum,
        "valor_previsto_periodo": pct_periodo * valor,
        "valor_previsto_acum": pct_acum * valor,
    }


def previsto_fases_lb_eap_j(
    valores_fase: dict[str, float],
    ano: int,
    mes: int,
) -> dict[str, dict[str, float]]:
    """Distribui o PV oficial da EAP J por fase.

    A linha total da Curva-S vem de PV_LB_ACUM_EAP_J. A tabela por fase do print
    e usada como distribuicao mensal; cada mes e ajustado ao total oficial para
    que o relatorio por fase feche com a mesma Curva-S.
    """
    if not valores_fase:
        return {}

    bac = sum(float(v or 0.0) for v in valores_fase.values())
    if not bac:
        return {}

    limite_iso = f"{ano:04d}-{mes:02d}-01"
    resultado = {
        str(codigo): {
            "pct_previsto_periodo": 0.0,
            "pct_previsto_acum": 0.0,
            "valor_previsto_periodo": 0.0,
            "valor_previsto_acum": 0.0,
        }
        for codigo in valores_fase
    }

    acumulado_total_anterior = 0.0
    for iso, pct_acum_total in sorted(PV_LB_ACUM_EAP_J.items()):
        total_mes_oficial = max(0.0, bac * (pct_acum_total / 100.0) - acumulado_total_anterior)
        acumulado_total_anterior = bac * (pct_acum_total / 100.0)
        if iso > limite_iso:
            break

        bruto_por_fase: dict[str, float] = {}
        for codigo, valor_fase in valores_fase.items():
            pct_mes_fase = PV_FASE_MENSAL_EAP_J.get(str(codigo), {}).get(iso, 0.0) / 100.0
            bruto_por_fase[str(codigo)] = float(valor_fase or 0.0) * pct_mes_fase

        total_bruto = sum(bruto_por_fase.values())
        fator = total_mes_oficial / total_bruto if total_bruto else 0.0

        for codigo, bruto in bruto_por_fase.items():
            valor_mes = bruto * fator
            resultado[codigo]["valor_previsto_acum"] += valor_mes
            if iso == limite_iso:
                valor_fase = float(valores_fase.get(codigo, 0.0) or 0.0)
                resultado[codigo]["valor_previsto_periodo"] = valor_mes
                resultado[codigo]["pct_previsto_periodo"] = valor_mes / valor_fase if valor_fase else 0.0

    for codigo, previsto in resultado.items():
        valor_fase = float(valores_fase.get(codigo, 0.0) or 0.0)
        previsto["pct_previsto_acum"] = previsto["valor_previsto_acum"] / valor_fase if valor_fase else 0.0

    return resultado


# ── Constantes de status ──────────────────────────────────────────────────────

STATUS_EM_PREVIA    = "em_previa"
STATUS_EM_ANALISE   = "em_analise"
STATUS_PRE_APROVADA = "pre_aprovada"
STATUS_FECHADA      = "fechada"
STATUS_CONSOLIDADA  = "consolidada"

STATUS_EDITAVEL = {STATUS_EM_PREVIA, STATUS_EM_ANALISE, STATUS_PRE_APROVADA}

# Transições permitidas via endpoint /status (somente fluxo de aprovação).
# Fechamento e consolidação NUNCA passam por aqui — têm endpoints próprios
# que executam a lógica financeira obrigatória.
TRANSICOES_STATUS_ENDPOINT: dict[str, list[str]] = {
    STATUS_EM_PREVIA:    [STATUS_EM_ANALISE],
    STATUS_EM_ANALISE:   [STATUS_PRE_APROVADA, STATUS_EM_PREVIA],   # permite retorno
    STATUS_PRE_APROVADA: [STATUS_EM_ANALISE],                       # só retorno; avanço é via /fechar
    STATUS_FECHADA:      [],    # terminal para o endpoint /status
    STATUS_CONSOLIDADA:  [],    # terminal para o endpoint /status
}

# Máquina de estados completa (usada internamente para validação)
TRANSICOES_COMPLETAS: dict[str, list[str]] = {
    STATUS_EM_PREVIA:    [STATUS_EM_ANALISE],
    STATUS_EM_ANALISE:   [STATUS_PRE_APROVADA, STATUS_EM_PREVIA],
    STATUS_PRE_APROVADA: [STATUS_FECHADA, STATUS_EM_ANALISE],
    STATUS_FECHADA:      [STATUS_CONSOLIDADA],
    STATUS_CONSOLIDADA:  [],
}

# Status da previsão mensal
PREV_EM_EDICAO  = "em_edicao"
PREV_FECHADA    = "fechada"
PREV_CONVERTIDA = "convertida"


# ── Helpers EAP ──────────────────────────────────────────────────────────────

def _carregar_eap(db: Session) -> tuple[list[EapItem], set[str], set[str]]:
    todos = db.query(EapItem).order_by(EapItem.codigo).all()
    pais  = {it.parent_codigo for it in todos if it.parent_codigo}
    folhas = {it.codigo for it in todos if it.codigo not in pais}
    return todos, folhas, pais


def _propagar_bottom_up(
    todos: list[EapItem],
    folhas: set[str],
    pct_por_codigo: dict[str, float],
) -> dict[str, float]:
    """Propaga % das folhas para os pais (bottom-up, ponderado por R$).

    Mesma lógica usada tanto para realizado quanto para previsto.
    Garante que o % de qualquer nó pai seja a média ponderada financeira
    dos seus filhos, nunca um valor arbitrário do mapa de entrada.
    """
    vals: dict[str, float] = dict(pct_por_codigo)

    # "peso" = valor financeiro EFETIVO de cada nó usado na ponderação.
    # Para nós com valor > 0 é o próprio valor (comportamento histórico).
    # Para nós com valor 0 (ex.: intermediário sintetizado ou linha-resumo sem
    # R$) o peso cai para a SOMA do peso dos filhos — assim a subárvore continua
    # contribuindo para os ancestrais em vez de zerar o ramo.
    peso: dict[str, float] = {}
    sorted_its = sorted(todos, key=lambda x: (-len(x.codigo), x.codigo))
    for it in sorted_its:
        filhos = [x for x in todos if x.parent_codigo == it.codigo]
        if it.codigo in folhas or not filhos:
            peso[it.codigo] = float(it.valor or 0.0)
            continue
        # Peso dos filhos: usa o efetivo já calculado (deepest-first garante ordem)
        soma = sum(peso.get(f.codigo, float(f.valor or 0.0)) * vals.get(f.codigo, 0.0)
                   for f in filhos)
        denom = float(it.valor or 0.0)
        if denom <= 0:
            denom = sum(peso.get(f.codigo, float(f.valor or 0.0)) for f in filhos)
        vals[it.codigo] = (soma / denom) if denom > 0 else 0.0
        peso[it.codigo] = float(it.valor or 0.0) or denom
    return vals


def _propagar_previsto(
    todos: list[EapItem],
    folhas: set[str],
    snaps: dict[str, float],
) -> dict[str, float]:
    """Propaga pct_previsto do snapshot para toda a hierarquia (bottom-up).

    Problema raiz: BmSnapshotPrevisao só contém folhas.  Quando _montar_de_*
    faz `snaps.get(pai, 0.0)`, qualquer nó não-folha retorna 0.  Isso faz o
    pct_previsto do pai aparecer como 0% na tela mesmo que os filhos tenham
    previsão lançada.

    Regra financeira:
      pct_previsto_pai = Σ(valor_filho × pct_previsto_filho) / valor_pai

    Equivalente ao `_propagar_bottom_up` do realizado — mesma ponderação.
    """
    # Parte do que existe no snapshot (folhas) e propaga para os pais.
    # A regra de Administracao Local replica a tela de Previsao Mensal:
    # entregas N.2 sem previsao propria herdam o percentual de N.1.
    pct_base = {cod: pct for cod, pct in snaps.items() if cod in folhas}
    vals = _propagar_bottom_up(todos, folhas, pct_base)

    codigos = {it.codigo for it in todos}
    filhos_por_pai: dict[str, list[EapItem]] = {}
    for it in todos:
        if it.parent_codigo:
            filhos_por_pai.setdefault(it.parent_codigo, []).append(it)

    for it in todos:
        if it.nivel != 2:
            continue
        descricao_norm = (it.descricao or "").lower()
        descricao_norm = descricao_norm.replace("ç", "c").replace("ã", "a")
        if "administracao local" not in descricao_norm:
            continue
        servico = f"{it.codigo.split('.')[0]}.1"
        if servico in codigos and it.codigo not in snaps:
            vals[it.codigo] = vals.get(servico, 0.0)

    for it in sorted(todos, key=lambda x: (-x.nivel, x.codigo)):
        if it.nivel != 1 or it.codigo in folhas or not it.valor:
            continue
        filhos = filhos_por_pai.get(it.codigo, [])
        if not filhos:
            continue
        soma = sum(float(f.valor or 0.0) * vals.get(f.codigo, 0.0) for f in filhos)
        vals[it.codigo] = soma / float(it.valor or 1.0)
    return vals


def _bac(db: Session) -> float:
    total = (
        db.query(func.sum(EapItem.valor))
        .filter(EapItem.nivel == 1)
        .scalar()
    ) or 0.0
    return float(total)


# ── Auditoria ─────────────────────────────────────────────────────────────────

def _log(
    db: Session,
    evento: str,
    ciclo_id: Optional[int] = None,
    usuario: Optional[str] = None,
    detalhe: Optional[dict] = None,
    antes: Optional[dict] = None,
    depois: Optional[dict] = None,
) -> None:
    db.add(BmLog(
        ciclo_id=ciclo_id,
        evento=evento,
        usuario=usuario,
        detalhe=json.dumps(detalhe, default=str) if detalhe else None,
        valor_antes=json.dumps(antes, default=str) if antes else None,
        valor_depois=json.dumps(depois, default=str) if depois else None,
    ))


# ── Previsão Mensal — gerenciamento de status ─────────────────────────────────


def _validar_previsao_hierarquia_100(db: Session, ano: int, mes: int) -> None:
    todos, folhas, _pais = _carregar_eap(db)
    filhos_por_pai: dict[str, list[EapItem]] = {}
    for it in todos:
        if it.parent_codigo:
            filhos_por_pai.setdefault(it.parent_codigo, []).append(it)

    pct_por_codigo = {
        p.eap_codigo: float(p.pct_previsto or 0.0)
        for p in db.query(EapPrevisaoMensal)
        .filter(EapPrevisaoMensal.ano == ano, EapPrevisaoMensal.mes == mes)
        .all()
    }

    valor_previsto: dict[str, float] = {}
    for it in sorted(todos, key=lambda x: (-len(x.codigo), x.codigo)):
        filhos = filhos_por_pai.get(it.codigo, [])
        if filhos:
            previsto = sum(valor_previsto.get(f.codigo, 0.0) for f in filhos)
        else:
            pct = max(0.0, min(100.0, pct_por_codigo.get(it.codigo, 0.0)))
            previsto = float(it.valor or 0.0) * pct / 100.0
        valor_previsto[it.codigo] = previsto
        limite = float(it.valor or 0.0)
        valor_filhos = sum(float(f.valor or 0.0) for f in filhos)
        hierarquia_inconsistente = filhos and limite > 0 and valor_filhos > limite + 0.01
        if filhos and limite > 0 and not hierarquia_inconsistente and previsto > limite + 0.01:
            raise ValueError(
                f"Previs?o excede 100% no item {it.codigo}: "
                f"R$ {previsto:.2f} previsto para limite R$ {limite:.2f}."
            )


def fechar_previsao_mensal(
    db: Session,
    ano: int,
    mes: int,
    fechado_por: Optional[str] = None,
) -> dict:
    """Congela a previsão do mês para permitir abertura do BM.

    Regras:
    - Não pode fechar previsão de mês com BM já fechado/consolidado
    - Marca todas as linhas em_edicao → fechada
    - Registra em BmLog
    """
    # Governança: competência deve estar aberta/em_apuracao
    assert_competencia_editavel(db, ano, mes)

    bm = db.query(BmCiclo).filter(BmCiclo.ano == ano, BmCiclo.mes == mes).first()
    if bm and bm.status in (STATUS_FECHADA, STATUS_CONSOLIDADA):
        raise ValueError(
            f"Não é possível alterar a previsão de {ano}/{mes:02d}: "
            f"o BM {bm.numero_bm} já está {bm.status}."
        )

    prevs = (
        db.query(EapPrevisaoMensal)
        .filter(
            EapPrevisaoMensal.ano == ano,
            EapPrevisaoMensal.mes == mes,
            EapPrevisaoMensal.status_previsao == PREV_EM_EDICAO,
        )
        .all()
    )

    if not prevs:
        # Verifica se existem mas já estão fechadas
        total = db.query(EapPrevisaoMensal).filter(
            EapPrevisaoMensal.ano == ano, EapPrevisaoMensal.mes == mes
        ).count()
        if total == 0:
            raise ValueError(f"Não há previsão lançada para {ano}/{mes:02d}.")
        raise ValueError(f"A previsão de {ano}/{mes:02d} já está fechada ou convertida.")

    _validar_previsao_hierarquia_100(db, ano, mes)

    for p in prevs:
        p.status_previsao = PREV_FECHADA

    db.flush()

    snapshot_recriado = 0
    if bm and bm.status == STATUS_EM_PREVIA:
        db.query(BmSnapshotPrevisao).filter(
            BmSnapshotPrevisao.ciclo_id == bm.id
        ).delete()
        snapshot_recriado = _criar_snapshot_previsao(db, bm)

    _log(db, "PREVISAO_FECHADA", usuario=fechado_por,
         detalhe={
             "ano": ano,
             "mes": mes,
             "itens_fechados": len(prevs),
             "bm_existente": bm.numero_bm if bm else None,
             "itens_snapshot_recriado": snapshot_recriado,
         })
    db.commit()
    return {
        "ano": ano,
        "mes": mes,
        "itens_fechados": len(prevs),
        "bm_existente": bm.numero_bm if bm else None,
        "itens_snapshot_recriado": snapshot_recriado,
    }


def reabrir_previsao_mensal(
    db: Session,
    ano: int,
    mes: int,
    reaberto_por: Optional[str] = None,
) -> dict:
    """Reabre previsão fechada para edição.

    Só permitido se não há BM aberto além de em_previa,
    e nunca se o BM já foi fechado/consolidado.
    Previsões 'convertida' não podem ser reabertas.
    """
    # Governança: competência deve estar aberta/em_apuracao
    assert_competencia_editavel(db, ano, mes)

    bm = db.query(BmCiclo).filter(BmCiclo.ano == ano, BmCiclo.mes == mes).first()
    if bm:
        if bm.status in (STATUS_FECHADA, STATUS_CONSOLIDADA):
            raise ValueError(
                f"Não é possível reabrir a previsão de {ano}/{mes:02d}: "
                f"o BM {bm.numero_bm} já está {bm.status}."
            )
        if bm.status != STATUS_EM_PREVIA:
            raise ValueError(
                f"Não é possível reabrir a previsão: o BM {bm.numero_bm} "
                f"está em '{bm.status}'. Devolva o BM para prévia primeiro."
            )

    prevs = (
        db.query(EapPrevisaoMensal)
        .filter(
            EapPrevisaoMensal.ano == ano,
            EapPrevisaoMensal.mes == mes,
            EapPrevisaoMensal.status_previsao == PREV_FECHADA,
        )
        .all()
    )

    if not prevs:
        raise ValueError(
            f"Não há previsões 'fechadas' para reabrir em {ano}/{mes:02d}. "
            "Previsões já 'convertidas' (BM aberto) não podem ser reabertas."
        )

    for p in prevs:
        p.status_previsao = PREV_EM_EDICAO

    # Se havia BM em prévia, invalida o snapshot dele (precisa reabrir o BM)
    if bm and bm.status == STATUS_EM_PREVIA:
        db.query(BmSnapshotPrevisao).filter(
            BmSnapshotPrevisao.ciclo_id == bm.id
        ).delete()
        _log(db, "SNAPSHOT_INVALIDADO", ciclo_id=bm.id, usuario=reaberto_por,
             detalhe={"motivo": "previsão reaberta após snapshot"})

    _log(db, "PREVISAO_REABERTA", usuario=reaberto_por,
         detalhe={"ano": ano, "mes": mes, "itens_reabertos": len(prevs)})
    db.commit()
    return {"ano": ano, "mes": mes, "itens_reabertos": len(prevs)}


# ── Abertura do BM ────────────────────────────────────────────────────────────

def abrir_bm(
    db: Session,
    ano: int,
    mes: int,
    criado_por: Optional[str] = None,
    observacao: Optional[str] = None,
) -> BmCiclo:
    """Abre (ou retorna existente) o BM do mês.

    Exige que a previsão do mês esteja fechada antes de criar o BM.
    Ao criar:
      1. Valida status da previsão
      2. Cria BmCiclo com status em_previa
      3. Tira snapshot imutável da previsão
      4. Marca previsões como 'convertida'
      5. Sincroniza com CicloMedicao legado
    """
    ciclo = db.query(BmCiclo).filter(BmCiclo.ano == ano, BmCiclo.mes == mes).first()
    if ciclo:
        if ciclo.status == STATUS_EM_PREVIA:
            snapshots = db.query(BmSnapshotPrevisao).filter(
                BmSnapshotPrevisao.ciclo_id == ciclo.id
            ).count()
            if snapshots == 0:
                prevs_prontas = db.query(EapPrevisaoMensal).filter(
                    EapPrevisaoMensal.ano == ano,
                    EapPrevisaoMensal.mes == mes,
                    EapPrevisaoMensal.status_previsao.in_([PREV_FECHADA, PREV_CONVERTIDA]),
                ).count()
                prevs_total = db.query(EapPrevisaoMensal).filter(
                    EapPrevisaoMensal.ano == ano,
                    EapPrevisaoMensal.mes == mes,
                ).count()
                if prevs_total > 0 and prevs_prontas == prevs_total:
                    _criar_snapshot_previsao(db, ciclo)
                    _log(db, "SNAPSHOT_RECRIADO", ciclo_id=ciclo.id, usuario=criado_por,
                         detalhe={"ano": ano, "mes": mes, "motivo": "BM existente sem snapshot"})
                    db.commit()
                    db.refresh(ciclo)
        return ciclo

    # ── Governança: garantir que competência existe e está aberta/em_apuracao ─
    # get_or_create cria como 'aberta' se não existir; assert valida o status
    get_or_create_competencia(db, ano, mes, criado_por=criado_por)
    assert_competencia_editavel(db, ano, mes)

    # ── Validação obrigatória de previsão ────────────────────────────────────
    # Regras (Ponto 2):
    #   1. Deve existir ao menos 1 item em eap_previsao_mensal para o mês
    #   2. TODOS os itens devem estar com status_previsao = "fechada" ou "convertida"
    # Sem previsão fechada não há base para tirar o snapshot imutável.
    prevs_total = db.query(EapPrevisaoMensal).filter(
        EapPrevisaoMensal.ano == ano, EapPrevisaoMensal.mes == mes
    ).count()

    if prevs_total == 0:
        raise ValueError(
            f"Não existe previsão mensal fechada para {ano}/{mes:02d}. "
            f"Lance a previsão via POST /api/eap/previsao/{ano}/{mes} "
            f"e feche-a via POST /api/bm/previsao/fechar antes de abrir o BM."
        )

    prevs_prontas = db.query(EapPrevisaoMensal).filter(
        EapPrevisaoMensal.ano == ano,
        EapPrevisaoMensal.mes == mes,
        EapPrevisaoMensal.status_previsao.in_([PREV_FECHADA, PREV_CONVERTIDA]),
    ).count()

    if prevs_prontas != prevs_total:
        itens_em_edicao = prevs_total - prevs_prontas
        raise ValueError(
            f"A previsão de {ano}/{mes:02d} ainda está em edição: "
            f"{itens_em_edicao} item(ns) pendente(s) de fechar. "
            f"Execute POST /api/bm/previsao/fechar para congelar todos os itens."
        )

    num_bm = _gerar_numero_bm(db, ano, mes)
    ciclo = BmCiclo(
        ano=ano, mes=mes,
        status=STATUS_EM_PREVIA,
        numero_bm=num_bm,
        criado_por=criado_por,
        observacao=observacao,
    )
    db.add(ciclo)
    db.flush()

    qtd_snap = _criar_snapshot_previsao(db, ciclo)

    # Sincroniza com legacy CicloMedicao
    ciclo_leg = db.query(CicloMedicao).filter(
        CicloMedicao.ano == ano, CicloMedicao.mes == mes
    ).first()
    if not ciclo_leg:
        ciclo_leg = CicloMedicao(ano=ano, mes=mes, status="aberto")
        db.add(ciclo_leg)
        db.flush()
    ciclo.ciclo_legado_id = ciclo_leg.id

    _log(db, "BM_ABERTO", ciclo_id=ciclo.id, usuario=criado_por,
         depois={"numero_bm": num_bm, "ano": ano, "mes": mes,
                 "itens_no_snapshot": qtd_snap})
    db.commit()
    db.refresh(ciclo)
    return ciclo


def _gerar_numero_bm(db: Session, ano: int, mes: int) -> str:
    return f"BM-{ano:04d}-{mes:02d}"


def _criar_snapshot_previsao(db: Session, ciclo: BmCiclo) -> int:
    """Snapshot imutável das previsões fechadas/convertidas do mês. Retorna qtd."""
    prevs = (
        db.query(EapPrevisaoMensal)
        .filter(
            EapPrevisaoMensal.ano == ciclo.ano,
            EapPrevisaoMensal.mes == ciclo.mes,
            EapPrevisaoMensal.status_previsao.in_([PREV_FECHADA, PREV_CONVERTIDA]),
        )
        .all()
    )
    count = 0
    for p in prevs:
        snap = BmSnapshotPrevisao(
            ciclo_id=ciclo.id,
            eap_codigo=p.eap_codigo,
            pct_previsto=float(p.pct_previsto or 0.0) / 100.0,  # 0-100 → 0-1
            adiantada=bool(p.adiantada),
            mes_origem_ano=p.mes_original_ano,
            mes_origem_mes=p.mes_original_mes,
        )
        db.add(snap)
        # Marca como convertida (bloqueia edição futura)
        p.status_previsao = PREV_CONVERTIDA
        count += 1
    return count


# ── Lançamentos ──────────────────────────────────────────────────────────────

def salvar_lancamentos(
    db: Session,
    ciclo_id: int,
    lancamentos: list[dict],  # [{eap_codigo, pct_acumulado 0-1, observacao}]
    salvo_por: Optional[str] = None,
) -> BmCiclo:
    """Salva lançamentos do BM com validações de integridade financeira.

    Validações obrigatórias:
    - BM deve estar em status editável
    - Somente folhas da EAP podem ser lançadas
    - pct_acumulado ∈ [0.0, 1.0]
    - pct_acumulado >= acumulado do último BM fechado (sem regressão)
    Cria nova versão no audit trail a cada save.
    """
    ciclo = _get_ciclo_ou_404(db, ciclo_id)
    _verificar_editavel(ciclo)

    # Governança: competência do mês do lançamento deve estar aberta/em_apuracao
    assert_competencia_editavel(db, ciclo.ano, ciclo.mes)

    todos, folhas, _ = _carregar_eap(db)
    folhas_map = {it.codigo: it for it in todos if it.codigo in folhas}
    pct_ant = _get_pct_acum_anterior(db, ciclo)

    erros: list[str] = []
    itens_antes: dict[str, float] = {}

    for item in lancamentos:
        codigo = item["eap_codigo"]
        pct    = float(item.get("pct_acumulado", 0.0))

        # 1. Somente folhas
        if codigo not in folhas_map:
            erros.append(f"{codigo}: não é folha da EAP (não pode ser lançado diretamente)")
            continue

        # 2. Range 0–100% — validação estrita via helper central
        try:
            pct = normalize_pct(pct, campo="pct_acumulado", codigo=codigo)
        except ValueError as exc:
            erros.append(str(exc))
            continue

        # 3. Sem regressão abaixo do acumulado consolidado
        pct_consolidado_anterior = pct_ant.get(codigo, 0.0)
        if pct < pct_consolidado_anterior - 1e-4:
            erros.append(
                f"{codigo}: pct_acumulado={pct:.4%} é menor que o acumulado "
                f"já consolidado={pct_consolidado_anterior:.4%}. "
                "Não é possível reduzir o acumulado histórico."
            )
            continue

        # 4. Teto: acumulado nunca pode ultrapassar 100%
        #    normalize_pct já garante pct ≤ 1.0, mas check_acumulado_teto
        #    é a defesa contra erros de propagação futura (bottom-up, soma, etc.)
        try:
            check_acumulado_teto(pct, campo="pct_acumulado", codigo=codigo)
        except ValueError as exc:
            erros.append(str(exc))
            continue

        # Registra estado anterior para audit trail
        lanc_atual = (
            db.query(BmLancamento)
            .filter(BmLancamento.ciclo_id == ciclo_id,
                    BmLancamento.eap_codigo == codigo)
            .first()
        )
        itens_antes[codigo] = float(lanc_atual.pct_acumulado) if lanc_atual else 0.0

        obs = item.get("observacao")
        if lanc_atual:
            lanc_atual.pct_acumulado = pct
            lanc_atual.observacao    = obs
            lanc_atual.atualizado_por = salvo_por
        else:
            db.add(BmLancamento(
                ciclo_id=ciclo_id,
                eap_codigo=codigo,
                pct_acumulado=pct,
                observacao=obs,
                atualizado_por=salvo_por,
            ))

        if ciclo.ciclo_legado_id:
            _espelhar_lancamento_legado(db, ciclo.ciclo_legado_id, codigo, pct, obs)

    if erros:
        raise ValueError("Erros de validação nos lançamentos:\n" + "\n".join(erros))

    versao = _criar_versao(db, ciclo, salvo_por)
    _log(db, "LANCAMENTO_SALVO", ciclo_id=ciclo_id, usuario=salvo_por,
         detalhe={"qtd_itens": len(lancamentos), "versao": versao.numero_versao},
         antes=itens_antes,
         depois={item["eap_codigo"]: item.get("pct_acumulado") for item in lancamentos})

    db.commit()
    db.refresh(ciclo)
    return ciclo


def _espelhar_lancamento_legado(
    db: Session,
    ciclo_leg_id: int,
    eap_codigo: str,
    pct_acumulado: float,
    observacao: Optional[str],
) -> None:
    lanc = (
        db.query(LancamentoMedicao)
        .filter(LancamentoMedicao.ciclo_id == ciclo_leg_id,
                LancamentoMedicao.eap_codigo == eap_codigo)
        .first()
    )
    if lanc:
        lanc.pct_acumulado = pct_acumulado
        lanc.observacao = observacao
    else:
        db.add(LancamentoMedicao(
            ciclo_id=ciclo_leg_id,
            eap_codigo=eap_codigo,
            pct_acumulado=pct_acumulado,
            observacao=observacao,
        ))


def _criar_versao(db: Session, ciclo: BmCiclo, criado_por: Optional[str]) -> BmVersao:
    num = (
        db.query(func.max(BmVersao.numero_versao))
        .filter(BmVersao.ciclo_id == ciclo.id)
        .scalar()
    ) or 0

    todos, folhas, _ = _carregar_eap(db)
    lancs = {l.eap_codigo: l.pct_acumulado for l in
             db.query(BmLancamento).filter(BmLancamento.ciclo_id == ciclo.id).all()}
    propagado = _propagar_bottom_up(todos, folhas, lancs)

    bac = _bac(db)
    nivel1_val = {it.codigo: float(it.valor or 0) for it in todos if it.nivel == 1}
    ev_acum = sum(propagado.get(cod, 0.0) * val for cod, val in nivel1_val.items())

    pct_ant = _get_pct_acum_anterior(db, ciclo)
    ev_ant = sum(pct_ant.get(cod, 0.0) * val for cod, val in nivel1_val.items())
    valor_periodo = ev_acum - ev_ant

    versao = BmVersao(
        ciclo_id=ciclo.id,
        numero_versao=num + 1,
        status_no_momento=ciclo.status,
        lancamentos_json=json.dumps([
            {"eap_codigo": k, "pct_acumulado": v} for k, v in lancs.items()
        ]),
        total_valor_periodo=valor_periodo,
        pct_acum_projeto=ev_acum / bac if bac else 0.0,
        criado_por=criado_por,
    )
    db.add(versao)
    return versao


# ── Transições de status (fluxo de aprovação) ────────────────────────────────

def transicionar_status(
    db: Session,
    ciclo_id: int,
    novo_status: str,
    usuario: Optional[str] = None,
    observacao: Optional[str] = None,
) -> BmCiclo:
    """Transiciona o status do BM via fluxo de aprovação.

    ATENÇÃO: Este método NÃO executa fechamento financeiro.
    Para fechar o BM use fechar_bm(). Para consolidar use consolidar_bm().
    Transições permitidas: em_previa ↔ em_analise ↔ pre_aprovada.
    """
    ciclo = _get_ciclo_ou_404(db, ciclo_id)

    # Guarda explícito: fechamento e consolidação têm fluxos próprios
    if novo_status == STATUS_FECHADA:
        raise ValueError(
            f"Transição para '{novo_status}' não é permitida pelo endpoint de status. "
            f"Use POST /bm/{ciclo_id}/fechar para fechar o BM."
        )
    if novo_status == STATUS_CONSOLIDADA:
        raise ValueError(
            f"Transição para '{novo_status}' não é permitida pelo endpoint de status. "
            f"Use POST /bm/{ciclo_id}/consolidar para consolidar o BM."
        )

    permitidos = TRANSICOES_STATUS_ENDPOINT.get(ciclo.status, [])
    if novo_status not in permitidos:
        raise ValueError(
            f"Transição inválida: '{ciclo.status}' → '{novo_status}'. "
            f"Transições permitidas neste status: {permitidos or ['nenhuma']}"
        )

    agora = _utcnow()
    status_anterior = ciclo.status

    if novo_status == STATUS_EM_ANALISE:
        ciclo.enviado_analise_em  = agora
        ciclo.enviado_analise_por = usuario
    elif novo_status == STATUS_PRE_APROVADA:
        ciclo.pre_aprovado_em  = agora
        ciclo.pre_aprovado_por = usuario

    if observacao:
        ciclo.observacao = observacao
    ciclo.status = novo_status

    _log(db, "STATUS_CHANGED", ciclo_id=ciclo_id, usuario=usuario,
         detalhe={"observacao": observacao},
         antes={"status": status_anterior},
         depois={"status": novo_status})
    db.commit()
    db.refresh(ciclo)
    return ciclo


# ── Fechamento do BM (evento financeiro principal) ────────────────────────────

def fechar_bm(
    db: Session,
    ciclo_id: int,
    fechado_por: Optional[str] = None,
    observacao: Optional[str] = None,
) -> BmCiclo:
    """Fecha o BM — transição financeiramente crítica.

    Exige obrigatoriamente status == pre_aprovada.
    Operação atômica: tudo ou nada.

    Ao fechar:
    1. Valida status (deve ser pre_aprovada)
    2. Muda status → fechada
    3. Materializa BmConsolidado (propagação hierárquica)
    4. Gera BmPendencia automaticamente
    5. Fecha CicloMedicao legado
    6. Registra em BmLog
    """
    ciclo = _get_ciclo_ou_404(db, ciclo_id)

    if ciclo.status == STATUS_FECHADA:
        raise ValueError(f"BM {ciclo.numero_bm} já está fechado.")
    if ciclo.status == STATUS_CONSOLIDADA:
        raise ValueError(f"BM {ciclo.numero_bm} já está consolidado.")
    if ciclo.status != STATUS_PRE_APROVADA:
        raise ValueError(
            f"BM {ciclo.numero_bm} não pode ser fechado: status atual é '{ciclo.status}'. "
            f"O BM deve estar 'pre_aprovada' antes do fechamento. "
            f"Fluxo obrigatório: em_previa → em_analise → pre_aprovada → fechada."
        )

    # ── Operação 100% atômica — um único commit ao final ────────────────────
    # Fluxo: 1.status  2.consolida  3.pendências  4.legado  5.log  6.commit
    # Se QUALQUER etapa falhar: get_db() garante rollback completo via except.
    # Nenhum dado parcial persiste em caso de erro.
    agora = _utcnow()
    ciclo.status     = STATUS_FECHADA
    ciclo.fechado_em  = agora
    ciclo.fechado_por = fechado_por
    if observacao:
        ciclo.observacao = observacao
    db.flush()  # garante que ciclo.id está visível para as etapas seguintes

    # Etapa 2: materializa o consolidado (snapshot financeiro imutável)
    _materializar_consolidado(db, ciclo)

    # Etapa 3: gera pendências (itens com previsto > realizado no período)
    qtd_pend = _gerar_pendencias(db, ciclo)

    # Etapa 4: espelha fechamento no CicloMedicao legado (unidirecional)
    if ciclo.ciclo_legado_id:
        leg = db.query(CicloMedicao).filter(
            CicloMedicao.id == ciclo.ciclo_legado_id
        ).first()
        if leg:
            leg.status     = "fechado"
            leg.fechado_em  = agora
            leg.fechado_por = fechado_por

    # Etapa 5: registra auditoria
    _log(db, "BM_FECHADO", ciclo_id=ciclo_id, usuario=fechado_por,
         detalhe={"observacao": observacao, "pendencias_geradas": qtd_pend},
         antes={"status": STATUS_PRE_APROVADA},
         depois={"status": STATUS_FECHADA})

    # Etapa 6: commit único — tudo ou nada
    db.commit()
    db.refresh(ciclo)
    return ciclo


# ── Consolidação do BM ────────────────────────────────────────────────────────

def consolidar_bm(
    db: Session,
    ciclo_id: int,
    consolidado_por: Optional[str] = None,
    observacao: Optional[str] = None,
) -> BmCiclo:
    """Consolida o BM — transição final após conferência pós-fechamento.

    Exige status == fechada.
    Após consolidar: status terminal, não pode ser alterado.
    """
    ciclo = _get_ciclo_ou_404(db, ciclo_id)

    if ciclo.status == STATUS_CONSOLIDADA:
        raise ValueError(f"BM {ciclo.numero_bm} já está consolidado.")
    if ciclo.status != STATUS_FECHADA:
        raise ValueError(
            f"BM {ciclo.numero_bm} não pode ser consolidado: status atual é '{ciclo.status}'. "
            "Apenas BMs com status 'fechada' podem ser consolidados."
        )

    agora = _utcnow()
    ciclo.status         = STATUS_CONSOLIDADA
    ciclo.consolidado_em  = agora
    ciclo.consolidado_por = consolidado_por
    if observacao:
        ciclo.observacao = observacao

    _log(db, "BM_CONSOLIDADO", ciclo_id=ciclo_id, usuario=consolidado_por,
         detalhe={"observacao": observacao},
         antes={"status": STATUS_FECHADA},
         depois={"status": STATUS_CONSOLIDADA})

    db.commit()
    db.refresh(ciclo)
    return ciclo


# ── Helpers de acumulado anterior ────────────────────────────────────────────

def _get_pct_acum_anterior(db: Session, ciclo: BmCiclo) -> dict[str, float]:
    """Busca o % acumulado de cada item no último BM fechado ANTES deste ciclo."""
    ciclo_ant = (
        db.query(BmCiclo)
        .filter(BmCiclo.status.in_([STATUS_FECHADA, STATUS_CONSOLIDADA]))
        .filter(
            (BmCiclo.ano < ciclo.ano) |
            ((BmCiclo.ano == ciclo.ano) & (BmCiclo.mes < ciclo.mes))
        )
        .order_by(BmCiclo.ano.desc(), BmCiclo.mes.desc())
        .first()
    )

    if ciclo_ant:
        consolidados = (
            db.query(BmConsolidado)
            .filter(BmConsolidado.ciclo_id == ciclo_ant.id)
            .all()
        )
        if consolidados:
            return {c.eap_codigo: c.pct_acumulado for c in consolidados}
        # Fallback: lançamentos do BM anterior (pré-refatoração)
        return {l.eap_codigo: l.pct_acumulado for l in
                db.query(BmLancamento)
                .filter(BmLancamento.ciclo_id == ciclo_ant.id).all()}

    # Fallback para CicloMedicao legado
    ciclo_leg = (
        db.query(CicloMedicao)
        .filter(CicloMedicao.status == "fechado")
        .filter(
            (CicloMedicao.ano < ciclo.ano) |
            ((CicloMedicao.ano == ciclo.ano) & (CicloMedicao.mes < ciclo.mes))
        )
        .order_by(CicloMedicao.ano.desc(), CicloMedicao.mes.desc())
        .first()
    )
    if not ciclo_leg:
        return {}
    return {l.eap_codigo: float(l.pct_acumulado) for l in
            db.query(LancamentoMedicao)
            .filter(LancamentoMedicao.ciclo_id == ciclo_leg.id).all()}


# ── Materialização do consolidado ─────────────────────────────────────────────

def _materializar_consolidado(db: Session, ciclo: BmCiclo) -> None:
    """Cria BmConsolidado para todos os itens EAP. Chamado SOMENTE por fechar_bm().

    BmConsolidado é IMUTÁVEL após ser escrito — não pode ser recalculado
    manualmente nem sobrescrito. Esta função é privada e deve ser chamada
    apenas uma vez por ciclo, durante o fechamento.
    """
    # Guard de imutabilidade: consolidado não pode ser recalculado.
    # Verifica se já existem registros — se sim, provavelmente é um bug no chamador.
    ja_existe = db.query(BmConsolidado).filter(
        BmConsolidado.ciclo_id == ciclo.id
    ).first()
    if ja_existe:
        raise ValueError(
            f"BM {ciclo.numero_bm}: BmConsolidado já existe para este ciclo. "
            "Recálculo manual do consolidado não é permitido — é imutável após fechamento."
        )

    todos, folhas, _ = _carregar_eap(db)

    lancs   = {l.eap_codigo: float(l.pct_acumulado) for l in
               db.query(BmLancamento).filter(BmLancamento.ciclo_id == ciclo.id).all()}
    pct_ant = _get_pct_acum_anterior(db, ciclo)
    snaps   = {s.eap_codigo: s.pct_previsto for s in
               db.query(BmSnapshotPrevisao)
               .filter(BmSnapshotPrevisao.ciclo_id == ciclo.id).all()}

    pct_base = {}
    for it in todos:
        if it.codigo in folhas:
            pct_base[it.codigo] = lancs.get(it.codigo, pct_ant.get(it.codigo, 0.0))

    pct_acum = _propagar_bottom_up(todos, folhas, pct_base)

    for it in todos:
        pct_atual    = pct_acum.get(it.codigo, 0.0)
        pct_ant_item = pct_ant.get(it.codigo, 0.0)
        pct_periodo  = max(0.0, pct_atual - pct_ant_item)
        val          = float(it.valor or 0.0)

        db.add(BmConsolidado(
            ciclo_id=ciclo.id,
            eap_codigo=it.codigo,
            pct_acumulado=pct_atual,
            pct_periodo=pct_periodo,
            pct_previsto=snaps.get(it.codigo, 0.0),
            valor_item=val,
            valor_periodo=pct_periodo * val,
            valor_acumulado=pct_atual * val,
            is_folha=it.codigo in folhas,
            nivel=it.nivel,
        ))


# ── Geração de pendências ─────────────────────────────────────────────────────

def _gerar_pendencias(db: Session, ciclo: BmCiclo) -> int:
    """Gera BmPendencia para cada folha onde previsto > realizado no período.

    Compara snapshot da previsão vs. pct_periodo do consolidado.
    Chamado SOMENTE por fechar_bm(). Pendências são imutáveis após geração
    (não podem ser removidas, apenas redistribuídas ou canceladas).
    Retorna quantidade gerada.
    """
    # Guard: não re-gera se já existem pendências para este ciclo
    ja_existe = db.query(BmPendencia).filter(
        BmPendencia.ciclo_id == ciclo.id
    ).first()
    if ja_existe:
        raise ValueError(
            f"BM {ciclo.numero_bm}: pendências já foram geradas para este ciclo. "
            "Não é permitido re-gerar pendências após fechamento."
        )

    # CRÍTICO: a sessão usa autoflush=False (ver database.py). O chamador
    # (fechar_bm) acabou de criar o BmConsolidado via db.add() SEM flush.
    # Sem este flush, a query de BmConsolidado abaixo NÃO enxerga as linhas
    # recém-adicionadas → `consolidados` viria vazio → toda folha cairia no
    # `if not cons: continue` e ZERO pendências seriam geradas (bug histórico).
    db.flush()

    snaps       = {s.eap_codigo: s.pct_previsto for s in
                   db.query(BmSnapshotPrevisao)
                   .filter(BmSnapshotPrevisao.ciclo_id == ciclo.id).all()}
    consolidados = {c.eap_codigo: c for c in
                    db.query(BmConsolidado)
                    .filter(BmConsolidado.ciclo_id == ciclo.id,
                            BmConsolidado.is_folha == True).all()}  # noqa: E712
    todos_eap = {it.codigo: it for it in db.query(EapItem).all()}

    THRESHOLD = 0.0001
    count = 0

    for codigo, pct_prev in snaps.items():
        cons     = consolidados.get(codigo)
        if not cons:
            continue  # item não é folha ou não existe no consolidado
        pct_real = cons.pct_periodo
        gap      = pct_prev - pct_real

        if gap <= THRESHOLD:
            continue

        it = todos_eap.get(codigo)
        if not it:
            continue

        val = float(it.valor or 0.0)
        db.add(BmPendencia(
            ciclo_id=ciclo.id,
            eap_codigo=codigo,
            pct_previsto=pct_prev,
            pct_realizado=pct_real,
            pct_gap=gap,
            valor_item=val,
            valor_gap=gap * val,
            status="ativa",
        ))
        count += 1

    return count


# ── Redistribuição de pendências ──────────────────────────────────────────────

def redistribuir_pendencia(
    db: Session,
    pendencia_id: int,
    destino_ano: int,
    destino_mes: int,
    pct_redistribuir: float,  # 0.0–1.0: fração do SALDO RESTANTE a redistribuir
    redistribuido_por: Optional[str] = None,
    observacao: Optional[str] = None,
) -> BmPendencia:
    """Redistribui parte ou total do saldo de uma pendência para mês futuro.

    pct_redistribuir é fração do SALDO RESTANTE (não do gap total):
      - 1.0 = redistribui tudo que ainda resta
      - 0.5 = redistribui metade do que ainda resta

    Validações:
    - Pendência deve estar ativa ou redistribuida_parcial
    - Mês destino NÃO pode ter BM fechado ou consolidado
    - pct_redistribuir ∈ (0, 1]
    """
    pend = db.query(BmPendencia).filter(BmPendencia.id == pendencia_id).first()
    if not pend:
        raise ValueError("Pendência não encontrada.")
    if pend.status == "redistribuida_total":
        raise ValueError("Pendência já foi totalmente redistribuída.")
    if pend.status == "cancelada":
        raise ValueError("Pendência cancelada não pode ser redistribuída.")

    # Governança: mês de DESTINO deve estar com competência aberta/em_apuracao
    assert_competencia_editavel(db, destino_ano, destino_mes)

    # Valida que mês destino não tem BM fechado
    bm_destino = (
        db.query(BmCiclo)
        .filter(
            BmCiclo.ano == destino_ano,
            BmCiclo.mes == destino_mes,
            BmCiclo.status.in_([STATUS_FECHADA, STATUS_CONSOLIDADA]),
        )
        .first()
    )
    if bm_destino:
        raise ValueError(
            f"Não é possível redistribuir para {destino_ano}/{destino_mes:02d}: "
            f"o BM {bm_destino.numero_bm} já está {bm_destino.status}. "
            "Redistribuição apenas para meses sem BM fechado."
        )

    # Validação estrita — sem tolerância de ponto-flutuante
    if pct_redistribuir <= 0.0:
        raise ValueError(
            f"pct_redistribuir inválido: {pct_redistribuir} ≤ 0. "
            "Deve ser maior que 0% (redistribuir ao menos algo)."
        )
    if pct_redistribuir > 1.0:
        raise ValueError(
            f"pct_redistribuir inválido: {pct_redistribuir} excede 100% (1.0). "
            "Valores permitidos: 0% até 100%."
        )

    # pct_real = fração do SALDO RESTANTE (não do gap total)
    saldo_restante = round(pend.pct_gap - pend.pct_ja_redistribuido, 8)
    if saldo_restante <= 1e-6:
        raise ValueError("Saldo de pendência é zero. Nada a redistribuir.")

    pct_real = round(saldo_restante * pct_redistribuir, 8)
    val      = round(pend.valor_item * pct_real, 2)

    redistrib = BmPendenciaRedistrib(
        pendencia_id=pend.id,
        destino_ano=destino_ano,
        destino_mes=destino_mes,
        pct_redistribuido=pct_real,
        valor_redistribuido=val,
        redistribuido_por=redistribuido_por,
        observacao=observacao,
    )
    db.add(redistrib)

    pend.pct_ja_redistribuido = round(pend.pct_ja_redistribuido + pct_real, 8)
    pend.mes_destino_ano = destino_ano
    pend.mes_destino_mes = destino_mes

    novo_saldo = round(pend.pct_gap - pend.pct_ja_redistribuido, 8)
    if novo_saldo <= 1e-4:
        pend.status = "redistribuida_total"
    elif pend.pct_ja_redistribuido > 1e-6:
        pend.status = "redistribuida_parcial"

    # Adiciona à previsão do mês destino
    pct_previsto_novo = pct_real * 100.0  # 0-1 → 0-100 (legado)
    prev_dest = (
        db.query(EapPrevisaoMensal)
        .filter(
            EapPrevisaoMensal.ano == destino_ano,
            EapPrevisaoMensal.mes == destino_mes,
            EapPrevisaoMensal.eap_codigo == pend.eap_codigo,
        )
        .first()
    )
    if prev_dest:
        if prev_dest.status_previsao == PREV_CONVERTIDA:
            raise ValueError(
                f"A previsão de {destino_ano}/{destino_mes:02d} para "
                f"{pend.eap_codigo} já foi convertida (BM aberto). "
                "Redistribua para outro mês ou feche/reabra o BM do destino."
            )
        prev_dest.pct_previsto = float(prev_dest.pct_previsto or 0.0) + pct_previsto_novo
    else:
        db.add(EapPrevisaoMensal(
            ano=destino_ano,
            mes=destino_mes,
            eap_codigo=pend.eap_codigo,
            pct_previsto=pct_previsto_novo,
            status_previsao=PREV_EM_EDICAO,
            observacao=f"Redistribuído de BM {pend.ciclo.numero_bm}",
        ))

    _log(db, "PENDENCIA_REDISTRIBUIDA", ciclo_id=pend.ciclo_id,
         usuario=redistribuido_por,
         detalhe={
             "pendencia_id": pend.id,
             "eap_codigo": pend.eap_codigo,
             "destino": f"{destino_ano}/{destino_mes:02d}",
             "pct_redistribuido": pct_real,
             "valor_redistribuido": val,
             "saldo_restante_apos": novo_saldo,
         })

    db.commit()
    db.refresh(pend)
    return pend


# ── Dashboard — somente dados consolidados ────────────────────────────────────

def get_curva_s_consolidada(db: Session) -> list[dict]:
    """Curva-S financeira PV × EV, restrita ao ESCOPO MEDIDO (apples-to-apples).

    Decisão de negócio (Achado B):
      - Escopo = folhas que entraram no SNAPSHOT de previsão de algum BM fechado
        (o universo que o BM se propôs a medir), aplicado de forma PROGRESSIVA por
        competência: em cada mês só contam as folhas já em escopo até aquele mês.
      - PV é a soma do baseline P6 (dist_mensal) APENAS dessas folhas — não do
        contrato inteiro — para o SPI comparar o mesmo universo do EV.
      - EV = valor acumulado consolidado das mesmas folhas.

    Também corrige o bug de back-fill do EV: antes, meses sem BM herdavam o EV
    final; agora o EV é 0 até o 1º BM e mantém o último valor conhecido por
    competência (degraus corretos).
    """
    todos   = db.query(EapItem).all()
    folhas  = set(_carregar_eap(db)[1])
    bac     = sum(float(it.valor or 0) for it in todos if it.nivel == 1)
    valor_folha = {it.codigo: float(it.valor or 0) for it in todos if it.codigo in folhas}

    # dist_mensal por folha (R$ absoluto por mês)
    dist_folha: dict[str, dict[str, float]] = {}
    for it in todos:
        if it.codigo in folhas and it.dist_mensal:
            try:
                dist_folha[it.codigo] = {m: float(v) for m, v in json.loads(it.dist_mensal).items()}
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

    ciclos_fechados = (
        db.query(BmCiclo)
        .filter(BmCiclo.status.in_([STATUS_FECHADA, STATUS_CONSOLIDADA]))
        .order_by(BmCiclo.ano, BmCiclo.mes)
        .all()
    )
    tem_previsao_cadastrada = db.query(EapPrevisaoMensal.id).first() is not None

    # Por competência (iso): folhas do snapshot + valor acumulado consolidado das folhas
    cycle_isos: list[str] = []
    snap_por_ciclo: dict[str, set[str]] = {}
    cons_por_ciclo: dict[str, dict[str, float]] = {}
    for ciclo in ciclos_fechados:
        iso = f"{ciclo.ano}-{ciclo.mes:02d}-01"
        cycle_isos.append(iso)
        snaps = db.query(BmSnapshotPrevisao).filter(BmSnapshotPrevisao.ciclo_id == ciclo.id).all()
        snap_por_ciclo[iso] = {s.eap_codigo for s in snaps if s.eap_codigo in folhas}
        cons = (db.query(BmConsolidado)
                .filter(BmConsolidado.ciclo_id == ciclo.id, BmConsolidado.nivel == 1)
                .all())
        cons_por_ciclo[iso] = sum(float(c.valor_acumulado or 0.0) for c in cons)

    # Eixo de meses = timeline do baseline (nível 1) ∪ competências dos BMs
    if tem_previsao_cadastrada or ciclos_fechados:
        pv_por_mes, pv_acum_por_mes = _pv_lb_eap_j(bac)
    else:
        pv_por_mes = {iso: 0.0 for iso in PV_LB_ACUM_EAP_J}
        pv_acum_por_mes = {iso: 0.0 for iso in PV_LB_ACUM_EAP_J}
    meses_axis = list(pv_acum_por_mes)
    todas_datas = sorted(set(meses_axis) | set(cycle_isos))

    pontos = []
    pv_acum_prev = ev_acum_prev = 0.0
    for iso in todas_datas:
        # Escopo progressivo: folhas já previstas em BMs até esta competência
        escopo: set[str] = set()
        for c_iso in cycle_isos:
            if c_iso <= iso:
                escopo |= snap_por_ciclo.get(c_iso, set())

        # PV acumulado = baseline das folhas do escopo, somado até o mês corrente
        pv_acum = pv_acum_por_mes.get(iso)
        if pv_acum is None:
            anteriores = [m for m in pv_acum_por_mes if m <= iso]
            pv_acum = pv_acum_por_mes[anteriores[-1]] if anteriores else 0.0

        # EV acumulado = consolidado da última competência fechada até aqui
        ev_acum = 0.0
        cic_ate = [c for c in cycle_isos if c <= iso]
        if cic_ate:
            ult = cic_ate[-1]
            ev_acum = cons_por_ciclo.get(ult, 0.0)

        # Cobertura do escopo medido sobre o BAC do contrato (transparência)
        cobertura = sum(valor_folha.get(f, 0.0) for f in escopo)

        pontos.append({
            "label": _label_mes(iso),
            "data": iso,
            "pv_mes": round(pv_por_mes.get(iso, max(0.0, pv_acum - pv_acum_prev)), 2),
            "ev_mes": round(ev_acum - ev_acum_prev, 2),
            "pv_acum": round(pv_acum, 2),
            "ev_acum": round(ev_acum, 2),
            "pct_pv": round(pv_acum / bac, 6) if bac else 0.0,
            "pct_ev": round(ev_acum / bac, 6) if bac else 0.0,
            "cobertura_pct": round(cobertura / bac, 6) if bac else 0.0,
            # Orçamento do escopo medido (Σ valor das folhas em escopo) — base
            # apples-to-apples para EAC/VAC, em vez do BAC do contrato inteiro.
            "bac_escopo": round(cobertura, 2),
        })
        pv_acum_prev, ev_acum_prev = pv_acum, ev_acum

    return pontos


def _calcular_ev_acum_legado(
    db: Session,
    ciclo: BmCiclo,
    todos: list[EapItem],
    nivel1_val: dict[str, float],
) -> float:
    if not ciclo.ciclo_legado_id:
        return 0.0
    pais   = {it.parent_codigo for it in todos if it.parent_codigo}
    folhas = {it.codigo for it in todos if it.codigo not in pais}
    lancs  = {l.eap_codigo: float(l.pct_acumulado) for l in
              db.query(LancamentoMedicao)
              .filter(LancamentoMedicao.ciclo_id == ciclo.ciclo_legado_id).all()}
    propagado = _propagar_bottom_up(todos, folhas, lancs)
    return sum(propagado.get(cod, 0.0) * val for cod, val in nivel1_val.items())


def _get_competencia_referencia(db: Session) -> tuple[int, int]:
    """Retorna (ano, mes) do último BM fechado/consolidado como competência de referência.

    Problema raiz de get_kpis_dashboard usar pontos[-1]:
      A curva-S planejada vai até o fim do projeto (ex.: Dez/2027).
      pontos[-1].pv_acum == BAC (100%) — o PV projetado ao final do contrato.
      Mas se hoje é Mai/2026, o PV acumulado de referência deveria ser o PV
      acumulado até Mai/2026, não o do fim do contrato.

      Usando pontos[-1] o dashboard mostra PV ≈ 100% mesmo quando a obra
      está 20% executada, tornando SPI e CPI completamente sem sentido.

    Competência de referência:
      1. Último BM fechado/consolidado (data mais recente)
      2. Mês atual, se não houver BM fechado ainda
    """
    from datetime import date as _date

    ultimo = (
        db.query(BmCiclo)
        .filter(BmCiclo.status.in_([STATUS_FECHADA, STATUS_CONSOLIDADA]))
        .order_by(BmCiclo.ano.desc(), BmCiclo.mes.desc())
        .first()
    )
    if ultimo:
        return (ultimo.ano, ultimo.mes)
    today = _date.today()
    return (today.year, today.month)


def _get_ponto_curva_por_competencia(
    pontos: list[dict],
    ref_ano: int,
    ref_mes: int,
) -> dict | None:
    """Localiza o ponto da curva-S correspondente à competência de referência.

    Busca o ponto exato pelo campo 'data' (ISO YYYY-MM-DD).
    Se não existir ponto exato, retorna o último ponto ANTERIOR à competência.
    Se todos os pontos são posteriores, retorna o primeiro.
    """
    if not pontos:
        return None
    ref_iso = f"{ref_ano}-{ref_mes:02d}-01"
    # Tenta match exato
    for p in pontos:
        if p["data"] == ref_iso:
            return p
    # Último ponto anterior à competência (obra que ainda não tem curva planejada
    # até a data de referência — usa o acumulado disponível mais recente)
    anteriores = [p for p in pontos if p["data"] <= ref_iso]
    if anteriores:
        return anteriores[-1]
    # Todos os pontos são futuros — usa o primeiro (competência antes do início)
    return pontos[0]


def get_kpis_dashboard(db: Session) -> dict:
    pontos = get_curva_s_consolidada(db)
    bac    = _bac(db)

    empty = {
        "bac": round(bac, 2), "pv": 0.0, "ev": 0.0,
        "spi": 0.0, "cv_pct": 0.0, "vac": 0.0,
        "pct_pv": 0.0, "pct_ev": 0.0, "ultimo_bm": None,
        "competencia_referencia": None,
        "pv_acum_referencia": 0.0, "ev_acum_referencia": 0.0,
        "pct_pv_referencia": 0.0, "pct_ev_referencia": 0.0,
        "spi_referencia": 0.0,
        # Cobertura do escopo medido (snapshot do BM) sobre o BAC do contrato.
        # SPI/PV agora são apples-to-apples: medem só o universo medido pelo BM.
        "cobertura_escopo_pct": 0.0,
        "bac_escopo": 0.0,
        "eac": 0.0,
    }
    if not pontos:
        return empty

    # ── Competência de referência ────────────────────────────────────────
    # Usa o último BM fechado/consolidado como âncora temporal.
    # NUNCA usa pontos[-1] porque este representa o fim do projeto planejado
    # (pv_acum == BAC), gerando SPI/PV incorretos quando a obra está em andamento.
    ref_ano, ref_mes = _get_competencia_referencia(db)
    ponto_ref = _get_ponto_curva_por_competencia(pontos, ref_ano, ref_mes)

    if ponto_ref is None:
        return empty

    pv = ponto_ref["pv_acum"]
    ev = ponto_ref["ev_acum"]
    spi = (ev / pv) if pv > 0 else 0.0
    cv_pct = ((ev - pv) / pv * 100) if pv > 0 else 0.0

    # EAC/VAC sobre o ORÇAMENTO DO ESCOPO MEDIDO (apples-to-apples com PV/EV),
    # não sobre o BAC do contrato — senão projeta-se o contrato inteiro no ritmo
    # de poucas folhas medidas, gerando VAC absurdo (ex.: -R$ 536 mi).
    bac_escopo = ponto_ref.get("bac_escopo", 0.0)
    eac = (bac_escopo / spi) if spi > 0 else bac_escopo
    vac = bac_escopo - eac

    competencia_str = f"{ref_ano}/{ref_mes:02d}"

    return {
        # ── Campos legados (mantidos para compatibilidade de frontend) ──
        # Agora refletem a competência de referência, não mais pontos[-1].
        "bac": bac,
        "pv": round(pv, 2),
        "ev": round(ev, 2),
        "spi": round(spi, 4),
        "cv_pct": round(cv_pct, 2),
        "vac": round(vac, 2),
        "pct_pv": round(pv / bac * 100, 2) if bac else 0.0,
        "pct_ev": round(ev / bac * 100, 2) if bac else 0.0,
        "ultimo_bm": competencia_str,
        # ── Campos novos (nominais por competência) ──────────────────────
        "competencia_referencia": competencia_str,
        "pv_acum_referencia": round(pv, 2),
        "ev_acum_referencia": round(ev, 2),
        "pct_pv_referencia": round(pv / bac * 100, 2) if bac else 0.0,
        "pct_ev_referencia": round(ev / bac * 100, 2) if bac else 0.0,
        "spi_referencia": round(spi, 4),
        # Cobertura do escopo medido (folhas no snapshot do BM) sobre o BAC.
        "cobertura_escopo_pct": round(ponto_ref.get("cobertura_pct", 0.0) * 100, 2),
        # Orçamento e EAC do escopo medido (base do VAC acima).
        "bac_escopo": round(bac_escopo, 2),
        "eac": round(eac, 2),
    }


def get_pendencias_ativas(
    db: Session,
    ano: Optional[int] = None,
    mes: Optional[int] = None,
    eap_codigo: Optional[str] = None,
) -> list[dict]:
    q = (
        db.query(BmPendencia, BmCiclo, EapItem)
        .join(BmCiclo, BmCiclo.id == BmPendencia.ciclo_id)
        .join(EapItem, EapItem.codigo == BmPendencia.eap_codigo)
        .filter(BmPendencia.status.in_(["ativa", "redistribuida_parcial"]))
    )
    if ano:
        q = q.filter(BmCiclo.ano == ano)
    if mes:
        q = q.filter(BmCiclo.mes == mes)
    if eap_codigo:
        q = q.filter(BmPendencia.eap_codigo == eap_codigo)

    q = q.order_by(BmCiclo.ano.desc(), BmCiclo.mes.desc(),
                   BmPendencia.valor_gap.desc())

    result = []
    for pend, ciclo, item in q.all():
        saldo = round(pend.pct_gap - pend.pct_ja_redistribuido, 8)
        result.append({
            "id": pend.id,
            "ciclo_id": ciclo.id,
            "numero_bm": ciclo.numero_bm,
            "ano_origem": ciclo.ano,
            "mes_origem": ciclo.mes,
            "eap_codigo": item.codigo,
            "eap_descricao": item.descricao,
            "nivel": item.nivel,
            "parent_codigo": item.parent_codigo,
            "valor_item": pend.valor_item,
            "pct_previsto":  round(pend.pct_previsto * 100, 4),
            "pct_realizado": round(pend.pct_realizado * 100, 4),
            "pct_gap":       round(pend.pct_gap * 100, 4),
            "valor_gap":     pend.valor_gap,
            "pct_saldo":     round(saldo * 100, 4),
            "valor_saldo":   round(saldo * pend.valor_item, 2),
            "status": pend.status,
            "redistribuicoes": [
                {
                    "destino": f"{r.destino_ano}/{r.destino_mes:02d}",
                    "pct": round(r.pct_redistribuido * 100, 4),
                    "valor": r.valor_redistribuido,
                    "em": r.redistribuido_em.isoformat() if r.redistribuido_em else None,
                    "por": r.redistribuido_por,
                }
                for r in pend.redistribuicoes
            ],
        })

    return result


# ── Montagem do BM completo ───────────────────────────────────────────────────

def montar_bm_completo(db: Session, ciclo_id: int) -> dict:
    ciclo = _get_ciclo_ou_404(db, ciclo_id)
    todos, folhas, _ = _carregar_eap(db)
    bac = sum(float(it.valor or 0) for it in todos if it.nivel == 1)

    if ciclo.status in (STATUS_FECHADA, STATUS_CONSOLIDADA):
        itens_out = _montar_de_consolidado(db, ciclo, todos, folhas)
    else:
        itens_out = _montar_de_lancamentos(db, ciclo, todos, folhas)

    # Agrega somente itens de nível 1 para evitar dupla-contagem pai+filho
    nivel1 = [i for i in itens_out if i["nivel"] == 1]

    total_valor_periodo  = sum(i["valor_periodo"]  for i in nivel1)
    total_valor_acum     = sum(i["valor_acumulado"] for i in nivel1)
    total_pct_periodo    = total_valor_periodo / bac if bac else 0.0
    total_pct_acum       = total_valor_acum / bac if bac else 0.0

    # Totais oficiais de previsto e desvio (novos campos — não quebram frontend)
    total_valor_previsto = sum(i.get("valor_previsto", 0.0) for i in nivel1)
    total_pct_previsto   = total_valor_previsto / bac if bac else 0.0
    desvio_valor_periodo = total_valor_periodo - total_valor_previsto
    desvio_pct_periodo   = total_pct_periodo - total_pct_previsto

    snaps = {s.eap_codigo: s for s in
             db.query(BmSnapshotPrevisao)
             .filter(BmSnapshotPrevisao.ciclo_id == ciclo_id).all()}

    pendencias = []
    if ciclo.status in (STATUS_FECHADA, STATUS_CONSOLIDADA):
        pendencias = get_pendencias_ativas(db, ano=ciclo.ano, mes=ciclo.mes)

    # Status da previsão do mês
    prevs_status = db.query(EapPrevisaoMensal.status_previsao).filter(
        EapPrevisaoMensal.ano == ciclo.ano,
        EapPrevisaoMensal.mes == ciclo.mes,
    ).distinct().all()
    status_previsao = list({s[0] for s in prevs_status}) if prevs_status else []

    return {
        "ciclo": {
            "id": ciclo.id,
            "ano": ciclo.ano,
            "mes": ciclo.mes,
            "numero_bm": ciclo.numero_bm,
            "status": ciclo.status,
            "criado_em": ciclo.criado_em.isoformat() if ciclo.criado_em else None,
            "enviado_analise_em": ciclo.enviado_analise_em.isoformat() if ciclo.enviado_analise_em else None,
            "pre_aprovado_em": ciclo.pre_aprovado_em.isoformat() if ciclo.pre_aprovado_em else None,
            "fechado_em": ciclo.fechado_em.isoformat() if ciclo.fechado_em else None,
            "fechado_por": ciclo.fechado_por,
            "consolidado_em": ciclo.consolidado_em.isoformat() if ciclo.consolidado_em else None,
            "observacao": ciclo.observacao,
        },
        "itens": itens_out,
        "bac": round(bac, 2),
        # ── Realizado ───────────────────────────────────────────────────
        "total_pct_acum": total_pct_acum,
        "total_pct_periodo": total_pct_periodo,
        "total_valor_periodo": total_valor_periodo,
        "total_valor_acum": total_valor_acum,
        # ── Previsto (novo — calculado com propagação hierárquica correta)
        "total_valor_previsto": total_valor_previsto,
        "total_pct_previsto": total_pct_previsto,
        # ── Desvio (novo — positivo = adiantado, negativo = atrasado)
        "desvio_valor_periodo": desvio_valor_periodo,
        "desvio_pct_periodo": desvio_pct_periodo,
        "pendencias": pendencias,
        "tem_snapshot_previsao": len(snaps) > 0,
        "qtd_itens_previstos": len(snaps),
        "status_previsao_mes": status_previsao,
    }


def _montar_de_consolidado(
    db: Session,
    ciclo: BmCiclo,
    todos: list[EapItem],
    folhas: set[str],
) -> list[dict]:
    cons_map = {c.eap_codigo: c for c in
                db.query(BmConsolidado).filter(BmConsolidado.ciclo_id == ciclo.id).all()}

    # BmConsolidado.pct_previsto só é correto para folhas — foi gravado
    # diretamente do snapshot.  Para pais o valor armazenado é 0 porque os
    # snapshots não têm registros para nós-pai.
    # Solução: recomputar a propagação em tempo de leitura a partir das folhas.
    snaps_raw = {cod: c.pct_previsto for cod, c in cons_map.items() if c.is_folha}
    pct_previsto_full = _propagar_previsto(todos, folhas, snaps_raw)

    result = []
    for it in sorted(todos, key=lambda x: x.codigo):
        c = cons_map.get(it.codigo)
        if not c:
            continue
        pct_prev = pct_previsto_full.get(it.codigo, 0.0)
        val      = float(c.valor_item or 0.0)
        result.append({
            "codigo": it.codigo,
            "descricao": it.descricao,
            "nivel": it.nivel,
            "parent_codigo": it.parent_codigo,
            "valor": val,
            "is_folha": c.is_folha,
            "pct_previsto": pct_prev,
            "valor_previsto": pct_prev * val,
            "pct_acum_anterior": c.pct_acumulado - c.pct_periodo,
            "pct_acumulado": c.pct_acumulado,
            "pct_periodo": c.pct_periodo,
            "valor_periodo": c.valor_periodo,
            "valor_acumulado": c.valor_acumulado,
            "observacao": None,
            "adiantada": False,
        })
    return result


def _montar_de_lancamentos(
    db: Session,
    ciclo: BmCiclo,
    todos: list[EapItem],
    folhas: set[str],
) -> list[dict]:
    lancs   = {l.eap_codigo: l for l in
               db.query(BmLancamento).filter(BmLancamento.ciclo_id == ciclo.id).all()}
    pct_ant = _get_pct_acum_anterior(db, ciclo)

    pct_base = {}
    for it in todos:
        if it.codigo in folhas:
            l = lancs.get(it.codigo)
            pct_anterior = float(pct_ant.get(it.codigo, 0.0) or 0.0)
            pct_lancado = float(l.pct_acumulado) if l else pct_anterior
            # Um lançamento zerado/regressivo não pode apagar o histórico já
            # consolidado. A medição do mês deve partir do acumulado anterior.
            pct_base[it.codigo] = max(pct_lancado, pct_anterior)

    pct_acum = _propagar_bottom_up(todos, folhas, pct_base)

    snaps_raw = {s.eap_codigo: s.pct_previsto for s in
                 db.query(BmSnapshotPrevisao)
                 .filter(BmSnapshotPrevisao.ciclo_id == ciclo.id).all()}
    snaps_codigos = set(snaps_raw)
    # Propaga previsto para toda a hierarquia — pais passam a exibir
    # a média ponderada financeira dos filhos, não zero.
    pct_previsto_full = _propagar_previsto(todos, folhas, snaps_raw)

    month_key = f"{ciclo.ano}-{ciclo.mes:02d}-01"
    result = []

    for it in sorted(todos, key=lambda x: x.codigo):
        pa_atual = pct_acum.get(it.codigo, 0.0)
        pa_ant   = pct_ant.get(it.codigo, 0.0) if it.codigo in folhas else (
            sum(float(f.valor or 0) * pct_ant.get(f.codigo, 0.0)
                for f in [x for x in todos if x.parent_codigo == it.codigo])
            / float(it.valor or 1.0) if it.valor else 0.0
        )
        periodo  = max(0.0, pa_atual - pa_ant)
        val      = float(it.valor or 0.0)
        pct_prev = pct_previsto_full.get(it.codigo, 0.0)
        previsto_folha_snapshot = it.codigo in snaps_codigos
        previsto_resumo_calculado = (it.codigo not in folhas) and pct_prev > 0.0

        try:
            dist = json.loads(it.dist_mensal) if it.dist_mensal else {}
        except Exception:
            dist = {}

        l = lancs.get(it.codigo)
        result.append({
            "codigo": it.codigo,
            "descricao": it.descricao,
            "nivel": it.nivel,
            "parent_codigo": it.parent_codigo,
            "valor": val,
            "is_folha": it.codigo in folhas,
            "pct_previsto": pct_prev,
            "valor_previsto": pct_prev * val,
            "previsto_folha_snapshot": previsto_folha_snapshot,
            "previsto_resumo_calculado": previsto_resumo_calculado,
            "pct_acum_anterior": pa_ant,
            "pct_acumulado": pa_atual,
            "pct_periodo": periodo,
            "valor_periodo": periodo * val,
            "valor_acumulado": pa_atual * val,
            "valor_dist_mes": float(dist.get(month_key, 0.0)),
            "observacao": l.observacao if l else None,
            "adiantada": False,
        })

    return result


# ── Helpers internos ──────────────────────────────────────────────────────────

def _get_ciclo_ou_404(db: Session, ciclo_id: int) -> BmCiclo:
    ciclo = db.query(BmCiclo).filter(BmCiclo.id == ciclo_id).first()
    if not ciclo:
        raise ValueError(f"BM id={ciclo_id} não encontrado.")
    return ciclo


def _verificar_editavel(ciclo: BmCiclo) -> None:
    if ciclo.status not in STATUS_EDITAVEL:
        raise ValueError(
            f"BM {ciclo.numero_bm} com status '{ciclo.status}' não pode ser editado. "
            f"Edição permitida apenas em: {sorted(STATUS_EDITAVEL)}"
        )


_MES_PT = {1: 'jan', 2: 'fev', 3: 'mar', 4: 'abr', 5: 'mai', 6: 'jun',
           7: 'jul', 8: 'ago', 9: 'set', 10: 'out', 11: 'nov', 12: 'dez'}


def _label_mes(iso: str) -> str:
    from datetime import date as _d
    d = _d.fromisoformat(iso)
    return f"{_MES_PT[d.month]}/{str(d.year)[2:]}"
