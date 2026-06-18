"""economico fase 1a importacao auditoria

Revision ID: f1a2b3c4d503
Revises: e4f5a6b7c802
Create Date: 2026-06-02
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect


revision = "f1a2b3c4d503"
down_revision = "e4f5a6b7c802"
branch_labels = None
depends_on = None


def _table_exists(conn, table: str) -> bool:
    return table in sa_inspect(conn).get_table_names()


def upgrade():
    conn = op.get_bind()
    if all(_table_exists(conn, table) for table in ("economico_importacao", "economico_valor", "economico_auditoria")):
        return

    op.create_table(
        "economico_importacao",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("arquivo_original", sa.String(), nullable=False),
        sa.Column("importado_em", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
        sa.Column("usuario", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "economico_valor",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("importacao_id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(), nullable=False),
        sa.Column("indicador", sa.String(), nullable=False),
        sa.Column("cenario", sa.String(), nullable=False),
        sa.Column("periodo", sa.Date(), nullable=True),
        sa.Column("categoria", sa.String(), nullable=True),
        sa.Column("valor", sa.Float(), nullable=True),
        sa.Column("origem", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["importacao_id"], ["economico_importacao.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_economico_valor_importacao_id", "economico_valor", ["importacao_id"])
    op.create_index("ix_economico_valor_tipo", "economico_valor", ["tipo"])
    op.create_index("ix_economico_valor_indicador", "economico_valor", ["indicador"])
    op.create_index("ix_economico_valor_cenario", "economico_valor", ["cenario"])
    op.create_index("ix_economico_valor_periodo", "economico_valor", ["periodo"])
    op.create_index("ix_economico_valor_categoria", "economico_valor", ["categoria"])

    op.create_table(
        "economico_auditoria",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("importacao_id", sa.Integer(), nullable=False),
        sa.Column("indicador", sa.String(), nullable=False),
        sa.Column("sistema", sa.Float(), nullable=True),
        sa.Column("resumo_bi", sa.Float(), nullable=True),
        sa.Column("diferenca", sa.Float(), nullable=True),
        sa.Column("aprovado", sa.Boolean(), nullable=True),
        sa.Column("tolerancia", sa.Float(), nullable=True),
        sa.Column("origem_sistema", sa.String(), nullable=True),
        sa.Column("origem_resumo_bi", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["importacao_id"], ["economico_importacao.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_economico_auditoria_importacao_id", "economico_auditoria", ["importacao_id"])


def downgrade():
    op.drop_index("ix_economico_auditoria_importacao_id", table_name="economico_auditoria")
    op.drop_table("economico_auditoria")
    op.drop_index("ix_economico_valor_categoria", table_name="economico_valor")
    op.drop_index("ix_economico_valor_periodo", table_name="economico_valor")
    op.drop_index("ix_economico_valor_cenario", table_name="economico_valor")
    op.drop_index("ix_economico_valor_indicador", table_name="economico_valor")
    op.drop_index("ix_economico_valor_tipo", table_name="economico_valor")
    op.drop_index("ix_economico_valor_importacao_id", table_name="economico_valor")
    op.drop_table("economico_valor")
    op.drop_table("economico_importacao")
