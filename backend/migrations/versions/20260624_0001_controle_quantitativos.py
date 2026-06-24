"""Cria tabela de quantitativos extraidos dos controles.

Revision ID: q1c2t3q4d624
Revises: r2c3t4s5a618
Create Date: 2026-06-24 11:30:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect


revision = "q1c2t3q4d624"
down_revision = "r2c3t4s5a618"
branch_labels = None
depends_on = None


def _tables(conn) -> set[str]:
    return set(sa_inspect(conn).get_table_names())


def upgrade() -> None:
    conn = op.get_bind()
    if "controle_quantitativos" in _tables(conn):
        return
    op.create_table(
        "controle_quantitativos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("controle_id", sa.Integer(), sa.ForeignKey("controles_documento.id"), nullable=False),
        sa.Column("codigo_controle", sa.String(), nullable=False),
        sa.Column("documento_origem", sa.String(), nullable=False),
        sa.Column("item", sa.String()),
        sa.Column("descricao", sa.Text()),
        sa.Column("unidade", sa.String(), nullable=False),
        sa.Column("quantidade", sa.Float(), nullable=False),
        sa.Column("fonte_arquivo", sa.Text()),
        sa.Column("evidencia", sa.Text()),
        sa.Column("status_validacao", sa.String(), default="Extraido automaticamente - revisar"),
        sa.Column("criado_em", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_controle_quantitativos_controle_id", "controle_quantitativos", ["controle_id"])
    op.create_index("ix_controle_quantitativos_codigo_controle", "controle_quantitativos", ["codigo_controle"])
    op.create_index("ix_controle_quantitativos_documento_origem", "controle_quantitativos", ["documento_origem"])
    op.create_index("ix_controle_quantitativos_unidade", "controle_quantitativos", ["unidade"])
    op.create_index("ix_controle_quantitativos_status_validacao", "controle_quantitativos", ["status_validacao"])


def downgrade() -> None:
    conn = op.get_bind()
    if "controle_quantitativos" not in _tables(conn):
        return
    op.drop_index("ix_controle_quantitativos_status_validacao", table_name="controle_quantitativos")
    op.drop_index("ix_controle_quantitativos_unidade", table_name="controle_quantitativos")
    op.drop_index("ix_controle_quantitativos_documento_origem", table_name="controle_quantitativos")
    op.drop_index("ix_controle_quantitativos_codigo_controle", table_name="controle_quantitativos")
    op.drop_index("ix_controle_quantitativos_controle_id", table_name="controle_quantitativos")
    op.drop_table("controle_quantitativos")
