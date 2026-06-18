"""Cria tabelas eap_item e tarefa_eap_link.

Suporta integração da EAP financeira com o cronograma para curva-S de
custo, EVM (Earned Value Management) e boletim de medição.

Revision ID: d42b7e5a8ef8
Revises: 7a9676a11c9a
Create Date: 2026-05-05 10:07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect


revision = 'd42b7e5a8ef8'
down_revision = '7a9676a11c9a'
branch_labels = None
depends_on = None


def _table_exists(conn, table: str) -> bool:
    return table in sa_inspect(conn).get_table_names()


def upgrade() -> None:
    conn = op.get_bind()
    if not _table_exists(conn, 'eap_item'):
        op.create_table(
            'eap_item',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('codigo', sa.String(), nullable=False),
            sa.Column('descricao', sa.String(), nullable=False),
            sa.Column('nivel', sa.Integer(), nullable=False),
            sa.Column('parent_codigo', sa.String(), nullable=True),
            sa.Column('valor', sa.Float(), server_default='0'),
            sa.Column('dist_mensal', sa.Text(), nullable=True),
            sa.Column('importado_em', sa.DateTime(), server_default=sa.func.now()),
            sa.UniqueConstraint('codigo'),
        )
        op.create_index('ix_eap_item_codigo', 'eap_item', ['codigo'])
        op.create_index('ix_eap_item_parent_codigo', 'eap_item', ['parent_codigo'])

    if not _table_exists(conn, 'tarefa_eap_link'):
        op.create_table(
            'tarefa_eap_link',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('tarefa_id', sa.Integer(),
                      sa.ForeignKey('tarefas.id'), nullable=False),
            sa.Column('eap_codigo', sa.String(),
                      sa.ForeignKey('eap_item.codigo'), nullable=False),
            sa.Column('peso', sa.Float(), server_default='1.0'),
            sa.Column('criado_em', sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index('ix_tarefa_eap_link_tarefa_id', 'tarefa_eap_link', ['tarefa_id'])
        op.create_index('ix_tarefa_eap_link_eap_codigo', 'tarefa_eap_link', ['eap_codigo'])


def downgrade() -> None:
    op.drop_index('ix_tarefa_eap_link_eap_codigo', 'tarefa_eap_link')
    op.drop_index('ix_tarefa_eap_link_tarefa_id', 'tarefa_eap_link')
    op.drop_table('tarefa_eap_link')
    op.drop_index('ix_eap_item_parent_codigo', 'eap_item')
    op.drop_index('ix_eap_item_codigo', 'eap_item')
    op.drop_table('eap_item')
