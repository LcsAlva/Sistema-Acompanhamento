"""Producao — unidades restantes (remaining) do ponderador para Tendência.

Revision ID: b7c8d9e10305
Revises: a6b7c8d90204
Create Date: 2026-06-02 14:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect


revision = 'b7c8d9e10305'
down_revision = 'a6b7c8d90204'
branch_labels = None
depends_on = None


def _col_exists(conn, table: str, col: str) -> bool:
    return col in {c["name"] for c in sa_inspect(conn).get_columns(table)}


def upgrade() -> None:
    conn = op.get_bind()
    if not _col_exists(conn, 'prod_atividade', 'unid_remaining'):
        op.add_column('prod_atividade', sa.Column('unid_remaining', sa.Float(), server_default='0'))


def downgrade() -> None:
    op.drop_column('prod_atividade', 'unid_remaining')
