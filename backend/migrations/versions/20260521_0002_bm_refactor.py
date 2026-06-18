"""Refatoração do módulo BM: auditoria, status de previsão, bloqueios.

Alterações:
  - eap_previsao_mensal: adiciona status_previsao (em_edicao|fechada|convertida)
    Marca como 'convertida' previsões de meses com BM fechado/consolidado.
  - bm_log: nova tabela de trilha de auditoria imutável
  - bm_ciclo: sem alteração estrutural (máquina de estados corrigida no código)

Revision ID: d9e8f7a6b502
Revises: c3a1b2d4e501
Create Date: 2026-05-21 00:02
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect, text

revision = 'd9e8f7a6b502'
down_revision = 'c3a1b2d4e501'
branch_labels = None
depends_on = None


def _col_exists(conn, table: str, col: str) -> bool:
    insp = sa_inspect(conn)
    return col in {c['name'] for c in insp.get_columns(table)}


def _table_exists(conn, table: str) -> bool:
    insp = sa_inspect(conn)
    return table in insp.get_table_names()


def upgrade() -> None:
    conn = op.get_bind()

    # ── status_previsao em eap_previsao_mensal ────────────────────────────
    if not _col_exists(conn, 'eap_previsao_mensal', 'status_previsao'):
        with op.batch_alter_table('eap_previsao_mensal') as batch:
            batch.add_column(
                sa.Column('status_previsao', sa.String(),
                          nullable=False, server_default='em_edicao')
            )

        # Marca como 'convertida' as previsões de meses com BM fechado/consolidado.
        # Isso garante que o novo fluxo não bloqueie meses já medidos.
        conn.execute(text("""
            UPDATE eap_previsao_mensal
            SET status_previsao = 'convertida'
            WHERE (ano, mes) IN (
                SELECT ano, mes FROM bm_ciclo
                WHERE status IN ('fechada', 'consolidada')
            )
        """))
        conn.commit()

    # ── bm_log: trilha de auditoria imutável ─────────────────────────────
    if not _table_exists(conn, 'bm_log'):
        op.create_table(
            'bm_log',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            # ciclo_id pode ser null para eventos de módulo (fechar previsão, etc.)
            sa.Column('ciclo_id', sa.Integer(),
                      sa.ForeignKey('bm_ciclo.id'), nullable=True),
            # Evento: BM_ABERTO | STATUS_CHANGED | LANCAMENTO_SALVO |
            #         BM_FECHADO | BM_CONSOLIDADO | PENDENCIA_REDISTRIBUIDA |
            #         PREVISAO_FECHADA | PREVISAO_REABERTA
            sa.Column('evento', sa.String(), nullable=False),
            sa.Column('usuario', sa.String(), nullable=True),
            sa.Column('detalhe', sa.Text(), nullable=True),    # JSON livre
            sa.Column('valor_antes', sa.Text(), nullable=True),  # JSON snapshot before
            sa.Column('valor_depois', sa.Text(), nullable=True), # JSON snapshot after
            sa.Column('criado_em', sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index('ix_bm_log_ciclo', 'bm_log', ['ciclo_id'])
        op.create_index('ix_bm_log_evento', 'bm_log', ['evento'])
        op.create_index('ix_bm_log_criado', 'bm_log', ['criado_em'])


def downgrade() -> None:
    conn = op.get_bind()
    if _table_exists(conn, 'bm_log'):
        op.drop_table('bm_log')

    if _col_exists(conn, 'eap_previsao_mensal', 'status_previsao'):
        with op.batch_alter_table('eap_previsao_mensal') as batch:
            batch.drop_column('status_previsao')
