"""
Diagnóstico permanente de INTEGRIDADE HIERÁRQUICA da EAP.

Garante a invariante:  folha -> pai -> ... -> nível 1  para 100% dos itens.

Verifica:
  1. Nós-pai referenciados (parent_codigo) que NÃO existem em eap_item (órfãos).
  2. Itens cuja cadeia até o nível 1 está QUEBRADA (não alcançam um nó nível 1).
  3. Incoerências de nível (nivel != nº de segmentos do código).
  4. parent_codigo incoerente com o código (não é o prefixo pontuado).
  5. Itens nível 1 sem valor; nós-pai com valor 0 (risco de propagação).
  6. Impacto financeiro (R$ e previsto) preso em subárvores órfãs.

Uso:
    python diagnostico_eap_integridade.py            # relatório
    python diagnostico_eap_integridade.py --strict   # exit code 1 se houver quebra (CI/health-gate)

NÃO altera nada no banco. Somente leitura.
"""
import sys
from collections import defaultdict
from backend.database import SessionLocal
from backend.models import EapItem, BmSnapshotPrevisao

# Console do Windows costuma usar cp1252; força UTF-8 para acentos/símbolos.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def parent_de(codigo: str):
    if not codigo or "." not in codigo:
        return None
    return ".".join(codigo.split(".")[:-1])


def brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def main(strict: bool) -> int:
    db = SessionLocal()
    try:
        items = db.query(EapItem).all()
        by_code = {it.codigo: it for it in items}
        codes = set(by_code)
        parents_ref = {it.parent_codigo for it in items if it.parent_codigo}

        print("=" * 80)
        print(f" INTEGRIDADE DA EAP — {len(items)} itens")
        print("=" * 80)

        # ── 1. Nós-pai referenciados que não existem ──────────────────────────
        orfaos = sorted(p for p in parents_ref if p not in codes)
        print(f"\n[1] Nós-pai referenciados AUSENTES em eap_item: {len(orfaos)}")
        for o in orfaos:
            # nó-pai do ausente existe? (reanexável a um avô existente?)
            avo = parent_de(o)
            avo_ok = (avo in codes) if avo else True
            filhos_diretos = [it.codigo for it in items if it.parent_codigo == o]
            print(f"   - {o:<16} (nível~{len(o.split('.'))})  avô '{avo}' existe={avo_ok}  "
                  f"filhos diretos órfãos={len(filhos_diretos)}: {filhos_diretos[:6]}")

        # ── 2. Cadeia até o nível 1 ───────────────────────────────────────────
        def caminho_ate_n1(cod):
            """Retorna (alcanca_n1, ponto_de_quebra|None, profundidade)."""
            visto = set()
            atual = cod
            while atual:
                if atual in visto:
                    return (False, f"ciclo em {atual}", len(visto))
                visto.add(atual)
                it = by_code.get(atual)
                if it is None:
                    return (False, atual, len(visto))  # quebra: nó ausente
                if it.nivel == 1 or it.parent_codigo is None:
                    return (True, None, len(visto))
                atual = it.parent_codigo
            return (False, "parent_codigo nulo sem nível 1", len(visto))

        quebrados = []
        for it in items:
            ok, quebra, _ = caminho_ate_n1(it.codigo)
            if not ok:
                quebrados.append((it, quebra))

        print(f"\n[2] Itens SEM cadeia completa até o nível 1: {len(quebrados)} "
              f"de {len(items)} ({100*len(quebrados)/max(len(items),1):.2f}%)")
        # agrupa por ponto de quebra
        por_quebra = defaultdict(list)
        for it, q in quebrados:
            por_quebra[q].append(it.codigo)
        for q, cods in sorted(por_quebra.items()):
            print(f"   quebra em '{q}': {len(cods)} item(ns) -> {cods[:8]}{'...' if len(cods)>8 else ''}")

        # ── 3. Incoerência de nível ───────────────────────────────────────────
        nivel_inconsistente = [it for it in items
                               if it.codigo and it.nivel != len(it.codigo.split("."))]
        print(f"\n[3] Itens com nível != nº de segmentos do código: {len(nivel_inconsistente)}")
        for it in nivel_inconsistente[:10]:
            print(f"   - {it.codigo:<16} nivel_gravado={it.nivel} segmentos={len(it.codigo.split('.'))}")

        # ── 4. parent_codigo != prefixo do código ─────────────────────────────
        parent_incoerente = [it for it in items
                             if it.parent_codigo != parent_de(it.codigo)]
        print(f"\n[4] Itens com parent_codigo != prefixo do código: {len(parent_incoerente)}")
        for it in parent_incoerente[:10]:
            print(f"   - {it.codigo:<16} parent_gravado={it.parent_codigo!r} esperado={parent_de(it.codigo)!r}")

        # ── 5. Valores de risco ───────────────────────────────────────────────
        nivel1 = [it for it in items if it.nivel == 1]
        n1_sem_valor = [it for it in nivel1 if not (it.valor or 0)]
        pais_valor_zero = [it for it in items if it.codigo in parents_ref and not (it.valor or 0)]
        print(f"\n[5] Itens nível 1: {len(nivel1)} | nível 1 sem valor: {len(n1_sem_valor)}")
        print(f"    Nós-pai com valor 0 (quebram _propagar_bottom_up): {len(pais_valor_zero)}")
        for it in pais_valor_zero[:10]:
            print(f"   - {it.codigo}")

        # ── 6. Impacto financeiro preso nas subárvores órfãs ──────────────────
        cods_quebrados = {it.codigo for it, _ in quebrados}
        folhas_quebradas = [it for it in items
                            if it.codigo in cods_quebrados and it.codigo not in parents_ref]
        valor_preso = sum(float(it.valor or 0) for it in folhas_quebradas)
        snaps = {s.eap_codigo for s in db.query(BmSnapshotPrevisao).all()}
        snaps_quebrados = sorted(snaps & cods_quebrados)
        print(f"\n[6] Folhas em subárvore órfã: {len(folhas_quebradas)} | "
              f"valor de folha preso fora do nível 1: {brl(valor_preso)}")
        print(f"    Itens de PREVISÃO (snapshot) que não alcançam o nível 1: "
              f"{len(snaps_quebrados)} -> {snaps_quebrados}")

        # ── Veredito ──────────────────────────────────────────────────────────
        # Quebra HARD = viola a invariante folha -> pai -> nível 1 (órfãos/sem cadeia).
        # Estas falham o --strict. As demais (nível!=segmentos, parent!=prefixo)
        # são AVISOS de qualidade que não quebram a cadeia.
        quebras_hard = len(orfaos) + len(quebrados)
        avisos = len(nivel_inconsistente) + len(parent_incoerente)
        print("\n" + "=" * 80)
        if quebras_hard == 0:
            print(" [OK] EAP ÍNTEGRA — toda folha alcança o nível 1 (invariante satisfeita).")
            if avisos:
                print(f"    (avisos não-bloqueantes: {avisos} item(ns) com nível/parent inconsistente)")
        else:
            print(f" [X] EAP COM QUEBRAS — {len(orfaos)} nós ausentes, "
                  f"{len(quebrados)} itens sem cadeia até o nível 1.")
            print("    Invariante 'folha -> pai -> nível 1' NÃO é satisfeita por 100% da EAP.")
        print("=" * 80)

        return 1 if (strict and quebras_hard) else 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main(strict="--strict" in sys.argv))
