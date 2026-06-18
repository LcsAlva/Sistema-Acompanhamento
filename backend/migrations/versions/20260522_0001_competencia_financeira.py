"""Competência Financeira — engine de governança mensal.

Cria as tabelas:
  - competencia_financeira : controle de status/lock por mês
  - competencia_log        : auditoria imutável de transições

Revision ID: a1b2c3d4e506
Revises:     f1a2b3c4d705
Create Date: 2026-05-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

# ── Identificadores Alembic ───────────────────────────────────────────────────
revision    = 'a1b2c3d4e506'
down_revision = 'f1a2b3c4d705'
branch_labels = None
depends_on    = None


def _table_exists(conn, table: str) -> bool:
    return table in sa_inspect(conn).get_table_names()


def upgrade() -> None:
    conn = op.get_bind()
    if _table_exists(conn, 'competencia_financeira') and _table_exists(conn, 'competencia_log'):
        return

    # ── competencia_financeira ────────────────────────────────────────────────
    op.create_table(
        'competencia_financeira',
        sa.Column('id',  sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('ano', sa.Integer(), nullable=False),
        sa.Column('mes', sa.Integer(), nullable=False),

        # Máquina de estados
        sa.Column('status', sa.String(), nullable=False, server_default='aberta'),
        sa.Column('locked', sa.Boolean(), nullable=False, server_default='0'),

        # Rastreabilidade de cada transição
        sa.Column('aberto_em',       sa.DateTime(), nullable=True),
        sa.Column('aberto_por',      sa.String(),   nullable=True),
        sa.Column('em_apuracao_em',  sa.DateTime(), nullable=True),
        sa.Column('em_apuracao_por', sa.String(),   nullable=True),
        sa.Column('fechado_em',      sa.DateTime(), nullable=True),
        sa.Column('fechado_por',     sa.String(),   nullable=True),
        sa.Column('consolidado_em',  sa.DateTime(), nullable=True),
        sa.Column('consolidado_por', sa.String(),   nullable=True),
        sa.Column('encerrado_em',    sa.DateTime(), nullable=True),
        sa.Column('encerrado_por',   sa.String(),   nullable=True),

        sa.Column('observacao',  sa.Text(),     nullable=True),
        sa.Column('created_at',  sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at',  sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),

        # Constraint: único por mês
        sa.UniqueConstraint('ano', 'mes', name='uq_competencia_ano_mes'),
    )

    # Índices para consultas frequentes
    op.create_index('ix_competencia_ano',    'competencia_financeira', ['ano'])
    op.create_index('ix_competencia_mes',    'competencia_financeira', ['mes'])
    op.create_index('ix_competencia_status', 'competencia_financeira', ['status'])

    # ── competencia_log ───────────────────────────────────────────────────────
    op.create_table(
        'competencia_log',
        sa.Column('id',             sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('competencia_id', sa.Integer(),
                  sa.ForeignKey('competencia_financeira.id'), nullable=False),
        sa.Column('evento',        sa.String(), nullable=False),
        sa.Column('status_antes',  sa.String(), nullable=True),
        sa.Column('status_depois', sa.String(), nullable=True),
        sa.Column('usuario',       sa.String(), nullable=True),
        sa.Column('observacao',    sa.Text(),   nullable=True),
        sa.Column('criado_em',     sa.DateTime(),
                  server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    op.create_index('ix_competencia_log_competencia_id',
                    'competencia_log', ['competencia_id'])
    op.create_index('ix_competencia_log_evento',
                    'competencia_log', ['evento'])
    op.create_index('ix_competencia_log_criado_em',
                    'competencia_log', ['criado_em'])


def downgrade() -> None:
    op.drop_table('competencia_log')
    op.drop_table('competencia_financeira')
