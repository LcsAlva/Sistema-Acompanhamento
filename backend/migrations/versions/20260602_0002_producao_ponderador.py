"""Producao Fase 1B — ponderacao por unidades fisicas (PONDERADOR URFCC).

Adiciona prod_atividade.unid_realizada (act_reg_qty do recurso ponderador).
A coluna 'peso' passa a armazenar as unidades orçadas (target_qty) do ponderador.

Revision ID: a6b7c8d90204
Revises: f5a6b7c80103
Create Date: 2026-06-02 12:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect


revision = 'a6b7c8d90204'
down_revision = 'f5a6b7c80103'
branch_labels = None
depends_on = None


def _col_exists(conn, table: str, col: str) -> bool:
    return col in {c["name"] for c in sa_inspect(conn).get_columns(table)}


def upgrade() -> None:
    conn = op.get_bind()
    if not _col_exists(conn, 'prod_atividade', 'unid_realizada'):
        op.add_column('prod_atividade', sa.Column('unid_realizada', sa.Float(), server_default='0'))


def downgrade() -> None:
    op.drop_column('prod_atividade', 'unid_realizada')
