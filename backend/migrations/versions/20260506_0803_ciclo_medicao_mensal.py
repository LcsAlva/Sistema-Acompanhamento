"""Adiciona tabelas e campos do ciclo de medição mensal.

- eap_item.criterio, eap_item.unidade (campos novos)
- eap_previsao_mensal: % previsto por item por mês
- eap_avanco_semanal: delta lançado por item por semana

Revision ID: 075cfb9d4358
Revises: d42b7e5a8ef8
Create Date: 2026-05-06 08:03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect


revision = '075cfb9d4358'
down_revision = 'd42b7e5a8ef8'
branch_labels = None
depends_on = None


def _table_exists(conn, table: str) -> bool:
    return table in sa_inspect(conn).get_table_names()


def _col_exists(conn, table: str, col: str) -> bool:
    return col in {c["name"] for c in sa_inspect(conn).get_columns(table)}


def upgrade() -> None:
    conn = op.get_bind()
    with op.batch_alter_table('eap_item', schema=None) as batch_op:
        if not _col_exists(conn, 'eap_item', 'criterio'):
            batch_op.add_column(sa.Column('criterio', sa.Text(), nullable=True))
        if not _col_exists(conn, 'eap_item', 'unidade'):
            batch_op.add_column(sa.Column('unidade', sa.String(), nullable=True, server_default='%'))

    if not _table_exists(conn, 'eap_previsao_mensal'):
        op.create_table(
            'eap_previsao_mensal',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('ano', sa.Integer(), nullable=False),
            sa.Column('mes', sa.Integer(), nullable=False),
            sa.Column('eap_codigo', sa.String(), sa.ForeignKey('eap_item.codigo'), nullable=False),
            sa.Column('pct_previsto', sa.Float(), server_default='0'),
            sa.Column('observacao', sa.Text(), nullable=True),
            sa.Column('lancado_em', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('lancado_por', sa.String(), nullable=True),
        )
        op.create_index('ix_eap_previsao_ano', 'eap_previsao_mensal', ['ano'])
        op.create_index('ix_eap_previsao_mes', 'eap_previsao_mensal', ['mes'])
        op.create_index('ix_eap_previsao_codigo', 'eap_previsao_mensal', ['eap_codigo'])
        op.create_index('uq_previsao_ano_mes_codigo', 'eap_previsao_mensal',
                        ['ano', 'mes', 'eap_codigo'], unique=True)

    if not _table_exists(conn, 'eap_avanco_semanal'):
        op.create_table(
            'eap_avanco_semanal',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('semana_codigo', sa.String(), nullable=False),
            sa.Column('eap_codigo', sa.String(), sa.ForeignKey('eap_item.codigo'), nullable=False),
            sa.Column('pct_delta', sa.Float(), server_default='0'),
            sa.Column('observacao', sa.Text(), nullable=True),
            sa.Column('lancado_em', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('lancado_por', sa.String(), nullable=True),
        )
        op.create_index('ix_eap_avanco_semana', 'eap_avanco_semanal', ['semana_codigo'])
        op.create_index('ix_eap_avanco_codigo', 'eap_avanco_semanal', ['eap_codigo'])


def downgrade() -> None:
    op.drop_index('ix_eap_avanco_codigo', 'eap_avanco_semanal')
    op.drop_index('ix_eap_avanco_semana', 'eap_avanco_semanal')
    op.drop_table('eap_avanco_semanal')

    op.drop_index('uq_previsao_ano_mes_codigo', 'eap_previsao_mensal')
    op.drop_index('ix_eap_previsao_codigo', 'eap_previsao_mensal')
    op.drop_index('ix_eap_previsao_mes', 'eap_previsao_mensal')
    op.drop_index('ix_eap_previsao_ano', 'eap_previsao_mensal')
    op.drop_table('eap_previsao_mensal')

    with op.batch_alter_table('eap_item', schema=None) as batch_op:
        batch_op.drop_column('unidade')
        batch_op.drop_column('criterio')
