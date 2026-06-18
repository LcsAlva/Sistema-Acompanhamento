"""Hardening arquitetural do módulo BM.

Alterações:
  - Índice composto em eap_previsao_mensal(ano, mes, status_previsao) para
    acelerar a validação de previsão ao abrir BM
  - Índice em bm_ciclo(ano, mes, status) para consultas de dashboard
  - Índice em bm_pendencia(ciclo_id, status) para consultas de redistribuição
  - Índice em bm_log(ciclo_id, criado_em DESC) para audit trail paginado
  - NÃO altera dados existentes
  - NÃO remove Base.metadata.create_all — isso foi feito no código (main.py)

Revision ID: e0f1a2b3c604
Revises: d9e8f7a6b502
Create Date: 2026-05-21 00:03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = 'e0f1a2b3c604'
down_revision = 'd9e8f7a6b502'
branch_labels = None
depends_on = None


def _index_exists(conn, index_name: str) -> bool:
    insp = sa_inspect(conn)
    for tbl in insp.get_table_names():
        for idx in insp.get_indexes(tbl):
            if idx['name'] == index_name:
                return True
    return False


def _col_exists(conn, table: str, col: str) -> bool:
    insp = sa_inspect(conn)
    return col in {c['name'] for c in insp.get_columns(table)}


def upgrade() -> None:
    conn = op.get_bind()

    # ── Índice composto para validação de previsão ao abrir BM ───────────
    # Usado em: SELECT COUNT WHERE ano=X AND mes=Y AND status_previsao IN (...)
    if not _index_exists(conn, 'ix_eap_prev_ano_mes_status'):
        op.create_index(
            'ix_eap_prev_ano_mes_status',
            'eap_previsao_mensal',
            ['ano', 'mes', 'status_previsao'],
        )

    # ── Índice para dashboard (BMs fechados/consolidados ordenados) ───────
    if not _index_exists(conn, 'ix_bm_ciclo_status_ano_mes'):
        op.create_index(
            'ix_bm_ciclo_status_ano_mes',
            'bm_ciclo',
            ['status', 'ano', 'mes'],
        )

    # ── Índice para consultas de redistribuição de pendências ─────────────
    if not _index_exists(conn, 'ix_bm_pendencia_ciclo_status'):
        op.create_index(
            'ix_bm_pendencia_ciclo_status',
            'bm_pendencia',
            ['ciclo_id', 'status'],
        )

    # ── Índice para audit trail paginado (ciclo + data desc) ─────────────
    if not _index_exists(conn, 'ix_bm_log_ciclo_criado'):
        op.create_index(
            'ix_bm_log_ciclo_criado',
            'bm_log',
            ['ciclo_id', 'criado_em'],
        )

    # ── Coluna numero_versao indexada em bm_versao ────────────────────────
    if not _index_exists(conn, 'ix_bm_versao_ciclo_num'):
        op.create_index(
            'ix_bm_versao_ciclo_num',
            'bm_versao',
            ['ciclo_id', 'numero_versao'],
        )

    # ── Índice por nível em bm_consolidado (dashboard de fase) ────────────
    if not _index_exists(conn, 'ix_bm_consolidado_nivel'):
        op.create_index(
            'ix_bm_consolidado_nivel',
            'bm_consolidado',
            ['ciclo_id', 'nivel'],
        )


def downgrade() -> None:
    conn = op.get_bind()
    for idx_name in [
        'ix_bm_consolidado_nivel',
        'ix_bm_versao_ciclo_num',
        'ix_bm_log_ciclo_criado',
        'ix_bm_pendencia_ciclo_status',
        'ix_bm_ciclo_status_ano_mes',
        'ix_eap_prev_ano_mes_status',
    ]:
        if _index_exists(conn, idx_name):
            # SQLite requer batch_alter para drop de index em algumas versões
            try:
                op.drop_index(idx_name)
            except Exception:
                pass
