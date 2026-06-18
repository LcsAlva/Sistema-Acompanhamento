"""Restrições CHECK de percentual financeiro — defesa de banco.

Adiciona CHECK CONSTRAINTS em todas as colunas de percentual para garantir
que mesmo um bypass de API/frontend não consiga persistir valores inválidos.

Regra financeira imutável:
  0.0 <= pct <= 1.0  (escala interna BM)
  0.0 <= pct <= 100  (escala legada eap_previsao_mensal.pct_previsto)

Tabelas protegidas:
  - bm_lancamento.pct_acumulado               [0.0, 1.0]
  - bm_snapshot_previsao.pct_previsto          [0.0, 1.0]
  - bm_consolidado.pct_acumulado              [0.0, 1.0]
  - bm_consolidado.pct_periodo                [0.0, 1.0]
  - bm_consolidado.pct_previsto               [0.0, 1.0]
  - bm_pendencia.pct_previsto                 [0.0, 1.0]
  - bm_pendencia.pct_realizado                [0.0, 1.0]
  - bm_pendencia.pct_gap                      [0.0, 1.0]
  - bm_pendencia.pct_ja_redistribuido         [0.0, 1.0]
  - bm_pendencia_redistrib.pct_redistribuido  [0.0, 1.0]
  - eap_previsao_mensal.pct_previsto          [0.0, 100.0]

NOTA SQLite:
  SQLite suporta CHECK constraints mas NÃO as aplica retroativamente em dados
  existentes (diferente de PostgreSQL). Para aplicar em dados pré-existentes,
  execute: PRAGMA integrity_check após a migration.

  Para PostgreSQL (produção): CHECK constraints são rigorosas e se aplicam
  imediatamente a qualquer INSERT/UPDATE.

Revision ID: f1a2b3c4d705
Revises: e0f1a2b3c604
Create Date: 2026-05-21 00:04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect, text

revision = 'f1a2b3c4d705'
down_revision = 'e0f1a2b3c604'
branch_labels = None
depends_on = None


def _constraint_exists(conn, table: str, constraint_name: str) -> bool:
    """Verifica se um CHECK constraint já existe (SQLite via sqlite_master)."""
    try:
        result = conn.execute(
            text(
                "SELECT COUNT(*) FROM sqlite_master "
                "WHERE type='table' AND name=:tbl AND sql LIKE :pat"
            ),
            {"tbl": table, "pat": f"%{constraint_name}%"},
        )
        return result.scalar() > 0
    except Exception:
        return False


def _table_exists(conn, table: str) -> bool:
    insp = sa_inspect(conn)
    return table in insp.get_table_names()


def upgrade() -> None:
    conn = op.get_bind()

    # ── bm_lancamento ────────────────────────────────────────────────────
    # pct_acumulado deve estar em [0.0, 1.0]
    if _table_exists(conn, 'bm_lancamento'):
        with op.batch_alter_table('bm_lancamento') as batch:
            batch.create_check_constraint(
                'ck_bm_lancamento_pct_acumulado',
                'pct_acumulado >= 0.0 AND pct_acumulado <= 1.0',
            )

    # ── bm_snapshot_previsao ─────────────────────────────────────────────
    if _table_exists(conn, 'bm_snapshot_previsao'):
        with op.batch_alter_table('bm_snapshot_previsao') as batch:
            batch.create_check_constraint(
                'ck_bm_snapshot_pct_previsto',
                'pct_previsto >= 0.0 AND pct_previsto <= 1.0',
            )

    # ── bm_consolidado ───────────────────────────────────────────────────
    if _table_exists(conn, 'bm_consolidado'):
        with op.batch_alter_table('bm_consolidado') as batch:
            batch.create_check_constraint(
                'ck_bm_consolidado_pct_acumulado',
                'pct_acumulado >= 0.0 AND pct_acumulado <= 1.0',
            )
            batch.create_check_constraint(
                'ck_bm_consolidado_pct_periodo',
                'pct_periodo >= 0.0 AND pct_periodo <= 1.0',
            )
            batch.create_check_constraint(
                'ck_bm_consolidado_pct_previsto',
                'pct_previsto >= 0.0 AND pct_previsto <= 1.0',
            )

    # ── bm_pendencia ─────────────────────────────────────────────────────
    if _table_exists(conn, 'bm_pendencia'):
        with op.batch_alter_table('bm_pendencia') as batch:
            batch.create_check_constraint(
                'ck_bm_pendencia_pct_previsto',
                'pct_previsto >= 0.0 AND pct_previsto <= 1.0',
            )
            batch.create_check_constraint(
                'ck_bm_pendencia_pct_realizado',
                'pct_realizado >= 0.0 AND pct_realizado <= 1.0',
            )
            batch.create_check_constraint(
                'ck_bm_pendencia_pct_redistribuido',
                'pct_ja_redistribuido >= 0.0 AND pct_ja_redistribuido <= 1.0',
            )

    # ── bm_pendencia_redistrib ───────────────────────────────────────────
    if _table_exists(conn, 'bm_pendencia_redistrib'):
        with op.batch_alter_table('bm_pendencia_redistrib') as batch:
            batch.create_check_constraint(
                'ck_bm_pendredist_pct',
                'pct_redistribuido > 0.0 AND pct_redistribuido <= 1.0',
            )

    # ── eap_previsao_mensal (escala legada 0–100) ────────────────────────
    if _table_exists(conn, 'eap_previsao_mensal'):
        with op.batch_alter_table('eap_previsao_mensal') as batch:
            batch.create_check_constraint(
                'ck_eap_prev_pct_previsto',
                'pct_previsto >= 0.0 AND pct_previsto <= 100.0',
            )


def downgrade() -> None:
    conn = op.get_bind()

    # SQLite: batch_alter para remover constraints (recria tabela sem elas)
    constraints_to_drop = [
        ('eap_previsao_mensal',    'ck_eap_prev_pct_previsto'),
        ('bm_pendencia_redistrib', 'ck_bm_pendredist_pct'),
        ('bm_pendencia',           'ck_bm_pendencia_pct_redistribuido'),
        ('bm_pendencia',           'ck_bm_pendencia_pct_realizado'),
        ('bm_pendencia',           'ck_bm_pendencia_pct_previsto'),
        ('bm_consolidado',         'ck_bm_consolidado_pct_previsto'),
        ('bm_consolidado',         'ck_bm_consolidado_pct_periodo'),
        ('bm_consolidado',         'ck_bm_consolidado_pct_acumulado'),
        ('bm_snapshot_previsao',   'ck_bm_snapshot_pct_previsto'),
        ('bm_lancamento',          'ck_bm_lancamento_pct_acumulado'),
    ]
    for table, cname in constraints_to_drop:
        if _table_exists(conn, table):
            try:
                with op.batch_alter_table(table) as batch:
                    batch.drop_constraint(cname, type_='check')
            except Exception:
                pass
