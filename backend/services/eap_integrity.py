"""Integridade hierárquica da EAP — síntese de intermediários + verificação (gate).

Invariante garantida: toda folha alcança o nível 1 via parent_codigo
(folha -> pai -> ... -> nível 1), para 100% dos itens.

Causa-raiz tratada: a planilha-fonte da EAP financeira OMITE linhas-resumo de
nível intermediário (ex.: existe '1.3.4.12' mas não existe '1.3.4'). O parser
deriva parent_codigo por prefixo do código, então esses pais ausentes geram
subárvores órfãs cujo valor/previsto/realizado nunca rola para o nível 1.

Este módulo:
  - sintetizar_intermediarios(itens): cria recursivamente os nós-pai ausentes,
    com valor = soma dos filhos e descrição marcada como sintetizada.
  - checar_integridade(itens): gate — retorna órfãos remanescentes e itens sem
    cadeia completa até o nível 1.

Opera sobre a lista de dicts produzida por parse_eap_xlsx (chaves: codigo,
descricao, nivel, parent_codigo, valor, dist_mensal), ANTES da persistência.
"""
from __future__ import annotations

DESC_SINTETIZADO = "[NÓ SINTETIZADO AUTOMATICAMENTE — ausente na EAP de origem]"


def parent_de(codigo: str) -> str | None:
    """De '1.3.4.12' devolve '1.3.4'. Para '1' (ou vazio) devolve None."""
    if not codigo or "." not in codigo:
        return None
    return ".".join(codigo.split(".")[:-1])


def _nivel_de(codigo: str) -> int:
    return len(codigo.split("."))


def sintetizar_intermediarios(itens: list[dict]) -> tuple[list[dict], list[dict]]:
    """Cria recursivamente os nós-pai ausentes referenciados pela hierarquia.

    Retorna (itens_completos, sintetizados), onde:
      - itens_completos = itens originais + nós sintetizados;
      - sintetizados    = apenas os nós criados (para auditoria/relatório).

    Regras:
      - Para cada código, sobe a cadeia de pais (por prefixo) até encontrar um
        código existente ou a raiz; todo elo ausente vira um nó sintetizado.
      - valor do nó sintetizado = Σ valor dos filhos diretos (bottom-up, então
        intermediários aninhados resolvem corretamente).
      - dist_mensal vazio (não toca PV/curva-S: essa só lê nível 1).
    """
    existentes = {it["codigo"] for it in itens}
    faltantes: set[str] = set()

    # 1. Descobre todos os elos ausentes subindo a cadeia de cada item.
    for it in itens:
        cur = parent_de(it["codigo"])
        while cur and cur not in existentes and cur not in faltantes:
            faltantes.add(cur)
            cur = parent_de(cur)

    # 2. Cria os nós sintetizados (valor 0 por enquanto).
    sintetizados: list[dict] = [
        {
            "codigo": cod,
            "descricao": DESC_SINTETIZADO,
            "nivel": _nivel_de(cod),
            "parent_codigo": parent_de(cod),
            "valor": 0.0,
            "dist_mensal": {},
            "sintetizado": True,
        }
        for cod in faltantes
    ]

    completos = list(itens) + sintetizados

    # 3. valor do sintetizado = Σ filhos diretos, processando do mais profundo
    #    para o mais raso (garante que intermediários aninhados já tenham valor).
    filhos_por_pai: dict[str, list[dict]] = {}
    for it in completos:
        p = it.get("parent_codigo")
        if p:
            filhos_por_pai.setdefault(p, []).append(it)

    for nd in sorted(sintetizados, key=lambda x: -_nivel_de(x["codigo"])):
        filhos = filhos_por_pai.get(nd["codigo"], [])
        nd["valor"] = round(sum(float(f.get("valor") or 0.0) for f in filhos), 6)

    return completos, sintetizados


def checar_integridade(itens: list[dict]) -> dict:
    """Gate de integridade. Retorna dict com órfãos e itens sem cadeia ao nível 1.

    {
      "ok": bool,
      "orfaos": [codigos de parent_codigo referenciados que não existem],
      "quebrados": [codigos de itens que não alcançam o nível 1],
      "total_itens": int,
    }
    """
    by_code = {it["codigo"]: it for it in itens}
    codes = set(by_code)
    parents_ref = {it["parent_codigo"] for it in itens if it.get("parent_codigo")}

    orfaos = sorted(p for p in parents_ref if p not in codes)

    def alcanca_n1(cod: str) -> bool:
        visto: set[str] = set()
        atual = cod
        while atual:
            if atual in visto:
                return False  # ciclo
            visto.add(atual)
            it = by_code.get(atual)
            if it is None:
                return False  # elo ausente
            if (it.get("nivel") == 1) or (it.get("parent_codigo") in (None, "")):
                return True
            atual = it["parent_codigo"]
        return False

    quebrados = sorted(c for c in codes if not alcanca_n1(c))

    return {
        "ok": (not orfaos and not quebrados),
        "orfaos": orfaos,
        "quebrados": quebrados,
        "total_itens": len(itens),
    }
