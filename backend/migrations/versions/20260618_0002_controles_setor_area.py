"""Adiciona setor e area aos controles vinculados a documentos.

Revision ID: r2c3t4s5a618
Revises: r1e2v3d4o618
Create Date: 2026-06-18 17:35:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect


revision = "r2c3t4s5a618"
down_revision = "r1e2v3d4o618"
branch_labels = None
depends_on = None


def _columns(conn, table: str) -> set[str]:
    return {col["name"] for col in sa_inspect(conn).get_columns(table)}


def upgrade() -> None:
    conn = op.get_bind()
    cols = _columns(conn, "controles_documento")
    if "setor" not in cols:
        op.add_column("controles_documento", sa.Column("setor", sa.String()))
        op.create_index("ix_controles_documento_setor", "controles_documento", ["setor"])
    if "area" not in cols:
        op.add_column("controles_documento", sa.Column("area", sa.String()))
        op.create_index("ix_controles_documento_area", "controles_documento", ["area"])


def downgrade() -> None:
    conn = op.get_bind()
    cols = _columns(conn, "controles_documento")
    if "area" in cols:
        op.drop_index("ix_controles_documento_area", table_name="controles_documento")
        op.drop_column("controles_documento", "area")
    if "setor" in cols:
        op.drop_index("ix_controles_documento_setor", table_name="controles_documento")
        op.drop_column("controles_documento", "setor")
