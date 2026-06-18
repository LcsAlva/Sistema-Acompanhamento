"""
validators.py — Helper central de validação financeira para percentuais.

REGRA IMUTÁVEL DO SISTEMA:
  Todo percentual de previsão ou medição deve estar no intervalo [0.0, 1.0]
  (representação interna 0–100%).

  - pct < 0.0   → inválido (negativo não existe em medição física)
  - pct > 1.0   → inválido (não se mede mais de 100% de nada)
  - NaN / None  → inválido
  - string      → convertido; se incontornável → inválido

USO:
  from utils.validators import normalize_pct

  pct = normalize_pct(raw_value, campo="pct_acumulado", codigo="1.1.1.1")

  Retorna float normalizado 0.0–1.0.
  Lança ValueError com mensagem padronizada se inválido.

ESCALA LEGADA:
  eap_previsao_mensal.pct_previsto usa escala 0–100 (legacy).
  Para validar campos nessa escala, use normalize_pct_100().
"""
from __future__ import annotations

import math


def normalize_pct(
    value,
    *,
    campo: str = "percentual",
    codigo: str = "",
) -> float:
    """
    Valida e normaliza um percentual na escala interna 0.0–1.0.

    Parâmetros
    ----------
    value  : qualquer — número, string (aceita '%' no final), etc.
    campo  : nome do campo para mensagem de erro
    codigo : código EAP / identificador para mensagem de erro

    Retorna
    -------
    float em [0.0, 1.0]

    Lança
    -----
    ValueError se fora do intervalo ou inválido.
    """
    prefix = f"{codigo}: " if codigo else ""

    # ── 1. Conversão de tipo ─────────────────────────────────────────────
    if value is None:
        raise ValueError(
            f"{prefix}{campo} inválido: valor nulo não é permitido. "
            "Valores permitidos: 0% até 100%."
        )

    if isinstance(value, str):
        cleaned = value.strip().rstrip("%").strip()
        if cleaned == "":
            raise ValueError(
                f"{prefix}{campo} inválido: string vazia. "
                "Valores permitidos: 0% até 100%."
            )
        try:
            value = float(cleaned)
        except ValueError:
            raise ValueError(
                f"{prefix}{campo} inválido: '{value}' não é numérico. "
                "Valores permitidos: 0% até 100%."
            )

    try:
        pct = float(value)
    except (TypeError, ValueError):
        raise ValueError(
            f"{prefix}{campo} inválido: tipo não conversível para float. "
            "Valores permitidos: 0% até 100%."
        )

    # ── 2. NaN / Inf ────────────────────────────────────────────────────
    if not math.isfinite(pct):
        raise ValueError(
            f"{prefix}{campo} inválido: valor não finito ({pct}). "
            "Valores permitidos: 0% até 100%."
        )

    # ── 3. Range estrito [0.0, 1.0] ─────────────────────────────────────
    if pct < 0.0:
        raise ValueError(
            f"{prefix}{campo} inválido: {pct:.6f} é negativo. "
            "Valores permitidos: 0% até 100%."
        )
    if pct > 1.0:
        raise ValueError(
            f"{prefix}{campo} inválido: {pct:.6f} excede 100% (1.0). "
            "Valores permitidos: 0% até 100%."
        )

    # ── 4. Normalização de ponto-flutuante (arredonda 10 casas) ─────────
    return round(pct, 10)


def normalize_pct_100(
    value,
    *,
    campo: str = "percentual",
    codigo: str = "",
) -> float:
    """
    Mesma lógica, mas para campos em escala 0–100 (legado: eap_previsao_mensal).

    Aceita 0–100 e converte para 0.0–1.0.
    Strings como "75.5%" ou "75.5" são aceitas.
    """
    prefix = f"{codigo}: " if codigo else ""

    if value is None:
        raise ValueError(
            f"{prefix}{campo} inválido: valor nulo. "
            "Valores permitidos: 0% até 100%."
        )

    if isinstance(value, str):
        cleaned = value.strip().rstrip("%").strip()
        if cleaned == "":
            raise ValueError(
                f"{prefix}{campo} inválido: string vazia. "
                "Valores permitidos: 0% até 100%."
            )
        try:
            value = float(cleaned)
        except ValueError:
            raise ValueError(
                f"{prefix}{campo} inválido: '{value}' não é numérico. "
                "Valores permitidos: 0% até 100%."
            )

    try:
        pct = float(value)
    except (TypeError, ValueError):
        raise ValueError(
            f"{prefix}{campo} inválido: tipo não conversível. "
            "Valores permitidos: 0% até 100%."
        )

    if not math.isfinite(pct):
        raise ValueError(
            f"{prefix}{campo} inválido: valor não finito ({pct}). "
            "Valores permitidos: 0% até 100%."
        )

    if pct < 0.0:
        raise ValueError(
            f"{prefix}{campo} inválido: {pct:.4f} é negativo. "
            "Valores permitidos: 0% até 100%."
        )
    if pct > 100.0:
        raise ValueError(
            f"{prefix}{campo} inválido: {pct:.4f} excede 100%. "
            "Valores permitidos: 0% até 100%."
        )

    return round(pct, 8)


def check_acumulado_teto(
    pct_acumulado: float,
    *,
    campo: str = "pct_acumulado",
    codigo: str = "",
) -> None:
    """
    Garante que o acumulado final não ultrapasse 100%.

    Deve ser chamado APÓS normalize_pct(), como segunda linha de defesa
    ao somar lançamentos + redistribuições.
    """
    prefix = f"{codigo}: " if codigo else ""
    if pct_acumulado > 1.0 + 1e-9:
        raise ValueError(
            f"{prefix}{campo} acumulado {pct_acumulado:.4%} excede 100%. "
            "O acumulado total de um item não pode ultrapassar 100% do seu valor contratual."
        )
