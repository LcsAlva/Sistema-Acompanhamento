"""
Diagnóstico de Pendências do BM — rastreia em qual etapa a pendência desaparece.

Uso:
    python diagnostico_pendencias.py [ano] [mes]
    python diagnostico_pendencias.py 2026 6        # default

Não altera nada no banco. Apenas lê e reporta o funil:
    itens previstos  ->  itens medidos  ->  itens com gap  ->  pendências geradas  ->  pendências exibidas
"""
import sys
from backend.database import SessionLocal
from backend.models import (
    BmCiclo, BmSnapshotPrevisao, BmConsolidado, BmPendencia,
    EapItem, EapPrevisaoMensal,
)
from backend.services import bm_service as svc

THRESHOLD = 0.0001  # mesmo threshold de _gerar_pendencias


def brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def main(ano: int, mes: int) -> None:
    db = SessionLocal()
    try:
        print("=" * 78)
        print(f" DIAGNÓSTICO DE PENDÊNCIAS  —  Competência {ano}/{mes:02d}")
        print("=" * 78)

        ciclo = db.query(BmCiclo).filter(BmCiclo.ano == ano, BmCiclo.mes == mes).first()
        if not ciclo:
            print(f"\n[X] Não existe BmCiclo para {ano}/{mes:02d}. Nada a diagnosticar.")
            return
        print(f"\nBM........: {ciclo.numero_bm}  (ciclo_id={ciclo.id})")
        print(f"Status....: {ciclo.status}")
        print(f"Fechado...: {ciclo.fechado_em}  por {ciclo.fechado_por}")
        print(f"Consolid..: {ciclo.consolidado_em}  por {ciclo.consolidado_por}")

        # valor de cada item EAP (por código, único)
        eap = {it.codigo: it for it in db.query(EapItem).all()}
        folhas = set(svc._carregar_eap(db)[1])  # conjunto de códigos-folha

        # ── ETAPA 1a: previsão LIVE (EapPrevisaoMensal) — o que a tela mostra ──
        print("\n" + "-" * 78)
        print(" ETAPA 1a — PREVISÃO LIVE (EapPrevisaoMensal)  [fonte da tela]")
        print("-" * 78)
        prevs_live = db.query(EapPrevisaoMensal).filter(
            EapPrevisaoMensal.ano == ano, EapPrevisaoMensal.mes == mes
        ).all()
        val_prev_live = 0.0
        for p in prevs_live:
            it = eap.get(p.eap_codigo)
            v = float(it.valor or 0) if it else 0.0
            val_prev_live += (float(p.pct_previsto or 0) / 100.0) * v
        print(f"  itens previstos (live)...: {len(prevs_live)}")
        print(f"  valor previsto (live)....: {brl(val_prev_live)}")
        st = {}
        for p in prevs_live:
            st[p.status_previsao] = st.get(p.status_previsao, 0) + 1
        print(f"  status_previsao..........: {st}")

        # ── ETAPA 1b: SNAPSHOT congelado (BmSnapshotPrevisao) — base de gap ──
        print("\n" + "-" * 78)
        print(" ETAPA 1b — SNAPSHOT DA PREVISÃO (BmSnapshotPrevisao)  [base do gap]")
        print("-" * 78)
        snaps = db.query(BmSnapshotPrevisao).filter(
            BmSnapshotPrevisao.ciclo_id == ciclo.id
        ).all()
        snap_map = {s.eap_codigo: float(s.pct_previsto or 0) for s in snaps}
        val_prev_snap = 0.0
        snap_zero = 0
        for s in snaps:
            it = eap.get(s.eap_codigo)
            v = float(it.valor or 0) if it else 0.0
            val_prev_snap += float(s.pct_previsto or 0) * v
            if float(s.pct_previsto or 0) <= THRESHOLD:
                snap_zero += 1
        print(f"  itens no snapshot........: {len(snaps)}")
        print(f"  itens com pct == 0.......: {snap_zero}")
        print(f"  valor previsto (snapshot): {brl(val_prev_snap)}")
        snap_nao_folha = [c for c in snap_map if c not in folhas]
        print(f"  códigos do snapshot que NÃO são folha: {len(snap_nao_folha)} {snap_nao_folha[:8]}")

        # ── ETAPA 2: MEDIDO (BmConsolidado folhas) ──
        print("\n" + "-" * 78)
        print(" ETAPA 2 — MEDIDO (BmConsolidado, is_folha=True)")
        print("-" * 78)
        cons = db.query(BmConsolidado).filter(
            BmConsolidado.ciclo_id == ciclo.id, BmConsolidado.is_folha == True  # noqa: E712
        ).all()
        cons_map = {c.eap_codigo: c for c in cons}
        val_medido = sum(float(c.valor_periodo or 0) for c in cons)
        print(f"  itens-folha consolidados.: {len(cons)}")
        print(f"  valor medido (período)...: {brl(val_medido)}")
        cons_total = db.query(BmConsolidado).filter(BmConsolidado.ciclo_id == ciclo.id).count()
        print(f"  total consolidado (todos): {cons_total}")
        if cons_total == 0:
            print("  [!] Nenhum BmConsolidado — fechar_bm() não materializou o consolidado.")

        # ── ETAPA 3: GAP por folha (réplica exata de _gerar_pendencias) ──
        print("\n" + "-" * 78)
        print(" ETAPA 3 — ITENS COM GAP (réplica de _gerar_pendencias)")
        print("-" * 78)
        gaps = []
        sem_consolidado = 0
        for codigo, pct_prev in snap_map.items():
            c = cons_map.get(codigo)
            if not c:
                sem_consolidado += 1
                continue
            gap = pct_prev - float(c.pct_periodo or 0)
            if gap <= THRESHOLD:
                continue
            it = eap.get(codigo)
            if not it:
                continue
            v = float(it.valor or 0)
            gaps.append((codigo, pct_prev, float(c.pct_periodo or 0), gap, gap * v))
        print(f"  códigos do snapshot SEM consolidado-folha (descartados): {sem_consolidado}")
        print(f"  itens com gap (deveriam virar pendência): {len(gaps)}")
        val_gap_total = sum(g[4] for g in gaps)
        print(f"  valor total dos gaps.....: {brl(val_gap_total)}")
        for codigo, pp, pr, g, vg in sorted(gaps, key=lambda x: -x[4])[:15]:
            print(f"    {codigo:<22} prev={pp*100:6.2f}%  med={pr*100:6.2f}%  "
                  f"gap={g*100:6.2f}%  {brl(vg)}")

        # ── ETAPA 4: PENDÊNCIAS GERADAS (BmPendencia) ──
        print("\n" + "-" * 78)
        print(" ETAPA 4 — PENDÊNCIAS GERADAS (tabela BmPendencia)")
        print("-" * 78)
        pend = db.query(BmPendencia).filter(BmPendencia.ciclo_id == ciclo.id).all()
        print(f"  registros em BmPendencia.: {len(pend)}")
        st_pend = {}
        for p in pend:
            st_pend[p.status] = st_pend.get(p.status, 0) + 1
        print(f"  status gravado...........: {st_pend or '(nenhum)'}")
        sem_eap = [p.eap_codigo for p in pend if p.eap_codigo not in eap]
        if sem_eap:
            print(f"  [!] pendências com eap_codigo SEM EapItem (somem no JOIN): {sem_eap}")

        # ── ETAPA 5: PENDÊNCIAS EXIBIDAS (get_pendencias_ativas / endpoint) ──
        print("\n" + "-" * 78)
        print(" ETAPA 5 — PENDÊNCIAS EXIBIDAS (get_pendencias_ativas — o que a tela recebe)")
        print("-" * 78)
        exib_mes = svc.get_pendencias_ativas(db, ano=ano, mes=mes)
        exib_todas = svc.get_pendencias_ativas(db)
        print(f"  exibidas p/ {ano}/{mes:02d}........: {len(exib_mes)}")
        print(f"  exibidas em /todas.......: {len(exib_todas)}")

        # ── FUNIL ──
        print("\n" + "=" * 78)
        print(" FUNIL DE DESAPARECIMENTO")
        print("=" * 78)
        print(f"  1a. previsão live...........: {len(prevs_live):>4}  ({brl(val_prev_live)})")
        print(f"  1b. snapshot congelado......: {len(snaps):>4}  ({brl(val_prev_snap)})")
        print(f"  2.  medido (folhas).........: {len(cons):>4}  ({brl(val_medido)})")
        print(f"  3.  itens com gap...........: {len(gaps):>4}  ({brl(val_gap_total)})")
        print(f"  4.  pendências geradas......: {len(pend):>4}")
        print(f"  5.  pendências exibidas.....: {len(exib_mes):>4}")

        print("\n  VEREDITO:")
        if len(prevs_live) > 0 and len(snaps) == 0:
            print("  >> Snapshot VAZIO apesar de previsão live existir.")
            print("     A pendência morre na ETAPA 1b: BM aberto sem previsão fechada,")
            print("     ou snapshot não capturado. _gerar_pendencias itera vazio.")
        elif val_prev_snap <= THRESHOLD and val_prev_live > THRESHOLD:
            print("  >> Snapshot existe mas com pct_previsto ZERADO, enquanto a tela")
            print("     mostra previsão > 0. A previsão foi editada DEPOIS de abrir o BM.")
            print("     A pendência morre na ETAPA 1b (gap = 0 - medido <= 0).")
        elif sem_consolidado > 0 and len(cons) > 0 and len(gaps) == 0:
            print("  >> Códigos do snapshot NÃO batem com folhas do consolidado.")
            print("     Mismatch de nível/código entre previsão e consolidado (ETAPA 3).")
        elif cons_total == 0:
            print("  >> Consolidado não materializado — BM não passou por fechar_bm().")
            print("     Foi só consolidado sem fechar? (ETAPA 2).")
        elif len(gaps) > 0 and len(pend) == 0:
            print("  >> Há gaps reais mas BmPendencia está VAZIA.")
            print("     _gerar_pendencias não rodou no fechamento OU houve rollback (ETAPA 4).")
        elif len(pend) > 0 and len(exib_mes) == 0:
            print("  >> Pendências existem mas não são exibidas.")
            print("     JOIN com EapItem/BmCiclo ou filtro de status as descarta (ETAPA 5).")
        elif len(gaps) == 0 and val_prev_snap > val_medido + 1.0:
            print("  >> Snapshot soma mais que o medido, mas nenhum gap por folha.")
            print("     Provável mismatch de código por folha (ETAPA 3) — investigar pareamento.")
        elif len(exib_mes) > 0:
            print("  >> Pendências EXISTEM e SÃO exibidas pelo backend.")
            print("     Se a tela está vazia, o problema é no frontend/refetch.")
        else:
            print("  >> Sem gaps por folha: previsto <= medido em todos os itens-folha")
            print("     individualmente. Conferir se o 'desvio' é só agregado/valor.")
        print()
    finally:
        db.close()


if __name__ == "__main__":
    ano = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
    mes = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    main(ano, mes)
