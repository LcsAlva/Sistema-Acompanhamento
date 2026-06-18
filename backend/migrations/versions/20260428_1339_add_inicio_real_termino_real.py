"""Adiciona colunas inicio_real e termino_real em programacao_semanal.

Datas reais preenchidas manualmente pelo planejador no modal do
Montar QPROG. Aparecem no PDF como "Programado" com prioridade
sobre as datas vindas do cronograma.

Revision ID: 7a9676a11c9a
Revises: 9c7d947b4dbc
Create Date: 2026-04-28 13:39:16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect


revision = '7a9676a11c9a'
down_revision = '9c7d947b4dbc'
branch_labels = None
depends_on = None


def _col_exists(conn, table: str, col: str) -> bool:
    return col in {c["name"] for c in sa_inspect(conn).get_columns(table)}


def upgrade() -> None:
    conn = op.get_bind()
    with op.batch_alter_table('programacao_semanal', schema=None) as batch_op:
        if not _col_exists(conn, 'programacao_semanal', 'inicio_real'):
            batch_op.add_column(sa.Column('inicio_real', sa.Date(), nullable=True))
        if not _col_exists(conn, 'programacao_semanal', 'termino_real'):
            batch_op.add_column(sa.Column('termino_real', sa.Date(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('programacao_semanal', schema=None) as batch_op:
        batch_op.drop_column('termino_real')
        batch_op.drop_column('inicio_real')
