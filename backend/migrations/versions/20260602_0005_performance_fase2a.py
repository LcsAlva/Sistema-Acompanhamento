"""performance fase 2a auditoria integrada

Revision ID: p2a3b4c5d605
Revises: f1c2d3e4f504
Create Date: 2026-06-02
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect


revision = "p2a3b4c5d605"
down_revision = "f1c2d3e4f504"
branch_labels = None
depends_on = None


def _table_exists(conn, table: str) -> bool:
    return table in sa_inspect(conn).get_table_names()


def upgrade():
    conn = op.get_bind()
    if _table_exists(conn, "performance_custo_classificacao") and _table_exists(conn, "performance_auditoria_mes"):
        return

    op.create_table(
        "performance_custo_classificacao",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("importacao_id", sa.Integer(), nullable=False),
        sa.Column("categoria_dre", sa.String(), nullable=False),
        sa.Column("classificacao", sa.String(), nullable=False),
        sa.Column("comportamento", sa.String(), nullable=True),
        sa.Column("risco_interpretacao", sa.Text(), nullable=True),
        sa.Column("regra", sa.Text(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
        sa.ForeignKeyConstraint(["importacao_id"], ["economico_importacao.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_performance_custo_classificacao_importacao_id", "performance_custo_classificacao", ["importacao_id"])
    op.create_index("ix_performance_custo_classificacao_categoria_dre", "performance_custo_classificacao", ["categoria_dre"])
    op.create_index("ix_performance_custo_classificacao_classificacao", "performance_custo_classificacao", ["classificacao"])

    op.create_table(
        "performance_auditoria_mes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("importacao_id", sa.Integer(), nullable=False),
        sa.Column("projeto_id", sa.Integer(), nullable=True),
        sa.Column("mes", sa.Date(), nullable=False),
        sa.Column("avanco_fisico_pct", sa.Float(), nullable=True),
        sa.Column("receita_acumulada", sa.Float(), nullable=True),
        sa.Column("custos_acumulados", sa.Float(), nullable=True),
        sa.Column("resultado_acumulado", sa.Float(), nullable=True),
        sa.Column("fonte_fisica", sa.String(), nullable=True),
        sa.Column("fonte_economica", sa.String(), nullable=True),
        sa.Column("riscos", sa.Text(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
        sa.ForeignKeyConstraint(["importacao_id"], ["economico_importacao.id"]),
        sa.ForeignKeyConstraint(["projeto_id"], ["prod_projeto.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_performance_auditoria_mes_importacao_id", "performance_auditoria_mes", ["importacao_id"])
    op.create_index("ix_performance_auditoria_mes_projeto_id", "performance_auditoria_mes", ["projeto_id"])
    op.create_index("ix_performance_auditoria_mes_mes", "performance_auditoria_mes", ["mes"])


def downgrade():
    op.drop_index("ix_performance_auditoria_mes_mes", table_name="performance_auditoria_mes")
    op.drop_index("ix_performance_auditoria_mes_projeto_id", table_name="performance_auditoria_mes")
    op.drop_index("ix_performance_auditoria_mes_importacao_id", table_name="performance_auditoria_mes")
    op.drop_table("performance_auditoria_mes")
    op.drop_index("ix_performance_custo_classificacao_classificacao", table_name="performance_custo_classificacao")
    op.drop_index("ix_performance_custo_classificacao_categoria_dre", table_name="performance_custo_classificacao")
    op.drop_index("ix_performance_custo_classificacao_importacao_id", table_name="performance_custo_classificacao")
    op.drop_table("performance_custo_classificacao")
