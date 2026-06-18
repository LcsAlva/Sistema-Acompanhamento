"""
Backfill de pendências para BMs fechados/consolidados ANTES da correção do
bug de flush em _gerar_pendencias.

Seguro e idempotente:
  - Só age em ciclos fechados/consolidados.
  - O guard de _gerar_pendencias impede regeração onde já existem pendências.
  - Usa exatamente a mesma lógica oficial (svc._gerar_pendencias).

Uso:
    python backfill_pendencias.py            # mostra o que faria (dry-run)
    python backfill_pendencias.py --apply    # grava as pendências faltantes
"""
import sys
from backend.database import SessionLocal
from backend.models import BmCiclo, BmPendencia
from backend.services import bm_service as svc

STATUS_ALVO = (svc.STATUS_FECHADA, svc.STATUS_CONSOLIDADA)


def main(apply: bool) -> None:
    db = SessionLocal()
    try:
        ciclos = (db.query(BmCiclo)
                  .filter(BmCiclo.status.in_(STATUS_ALVO))
                  .order_by(BmCiclo.ano, BmCiclo.mes).all())
        print(f"Modo: {'APPLY (gravando)' if apply else 'DRY-RUN (simulação)'}")
        print(f"BMs fechados/consolidados: {len(ciclos)}\n")
        total = 0
        for c in ciclos:
            ja = db.query(BmPendencia).filter(BmPendencia.ciclo_id == c.id).count()
            if ja > 0:
                print(f"  {c.numero_bm}: já possui {ja} pendência(s) — pulando.")
                continue
            qtd = svc._gerar_pendencias(db, c)  # guard interno + flush corrigido
            total += qtd
            print(f"  {c.numero_bm}: geradas {qtd} pendência(s).")
            if not apply:
                db.rollback()  # descarta no dry-run
        if apply:
            db.commit()
            print(f"\n[OK] Backfill aplicado. Total de pendências criadas: {total}")
        else:
            print(f"\n[DRY-RUN] Seriam criadas {total} pendência(s). "
                  f"Rode com --apply para gravar.")
    finally:
        db.close()


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
