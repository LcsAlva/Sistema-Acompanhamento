"""economico fase 1c investigacao custos desvios

Revision ID: f1c2d3e4f504
Revises: f1a2b3c4d503
Create Date: 2026-06-02
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect


revision = "f1c2d3e4f504"
down_revision = "f1a2b3c4d503"
branch_labels = None
depends_on = None


def _table_exists(conn, table: str) -> bool:
    return table in sa_inspect(conn).get_table_names()


def upgrade():
    conn = op.get_bind()
    if all(_table_exists(conn, table) for table in (
        "economico_resumo_calculado",
        "economico_lancamento_razao",
        "economico_relatorio_oc",
        "economico_analise_dre",
        "economico_conta_despesa",
    )):
        return

    op.create_table(
        "economico_resumo_calculado",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("importacao_id", sa.Integer(), nullable=False),
        sa.Column("indicador", sa.String(), nullable=False),
        sa.Column("cenario", sa.String(), nullable=False),
        sa.Column("periodo", sa.Date(), nullable=True),
        sa.Column("categoria", sa.String(), nullable=True),
        sa.Column("valor", sa.Float(), nullable=True),
        sa.Column("origem", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["importacao_id"], ["economico_importacao.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_economico_resumo_calculado_importacao_id", "economico_resumo_calculado", ["importacao_id"])
    op.create_index("ix_economico_resumo_calculado_indicador", "economico_resumo_calculado", ["indicador"])
    op.create_index("ix_economico_resumo_calculado_cenario", "economico_resumo_calculado", ["cenario"])
    op.create_index("ix_economico_resumo_calculado_periodo", "economico_resumo_calculado", ["periodo"])
    op.create_index("ix_economico_resumo_calculado_categoria", "economico_resumo_calculado", ["categoria"])

    op.create_table(
        "economico_lancamento_razao",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("importacao_id", sa.Integer(), nullable=False),
        sa.Column("data", sa.Date(), nullable=True),
        sa.Column("documento", sa.String(), nullable=True),
        sa.Column("fornecedor", sa.String(), nullable=True),
        sa.Column("conta", sa.String(), nullable=True),
        sa.Column("conta_descricao", sa.String(), nullable=True),
        sa.Column("categoria_dre", sa.String(), nullable=True),
        sa.Column("historico", sa.Text(), nullable=True),
        sa.Column("valor", sa.Float(), nullable=True),
        sa.Column("tipo", sa.String(), nullable=True),
        sa.Column("lote", sa.String(), nullable=True),
        sa.Column("lancamento", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["importacao_id"], ["economico_importacao.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_economico_lancamento_razao_importacao_id", "economico_lancamento_razao", ["importacao_id"])
    op.create_index("ix_economico_lancamento_razao_data", "economico_lancamento_razao", ["data"])
    op.create_index("ix_economico_lancamento_razao_documento", "economico_lancamento_razao", ["documento"])
    op.create_index("ix_economico_lancamento_razao_fornecedor", "economico_lancamento_razao", ["fornecedor"])
    op.create_index("ix_economico_lancamento_razao_conta", "economico_lancamento_razao", ["conta"])
    op.create_index("ix_economico_lancamento_razao_categoria_dre", "economico_lancamento_razao", ["categoria_dre"])

    op.create_table(
        "economico_relatorio_oc",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("importacao_id", sa.Integer(), nullable=False),
        sa.Column("numero_oc", sa.String(), nullable=True),
        sa.Column("item_oc", sa.String(), nullable=True),
        sa.Column("requisicao", sa.String(), nullable=True),
        sa.Column("produto", sa.String(), nullable=True),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("fornecedor", sa.String(), nullable=True),
        sa.Column("data", sa.Date(), nullable=True),
        sa.Column("conta", sa.String(), nullable=True),
        sa.Column("conta_descricao", sa.String(), nullable=True),
        sa.Column("valor_total", sa.Float(), nullable=True),
        sa.Column("valor_liquido", sa.Float(), nullable=True),
        sa.Column("valor_nf", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["importacao_id"], ["economico_importacao.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_economico_relatorio_oc_importacao_id", "economico_relatorio_oc", ["importacao_id"])
    op.create_index("ix_economico_relatorio_oc_numero_oc", "economico_relatorio_oc", ["numero_oc"])
    op.create_index("ix_economico_relatorio_oc_fornecedor", "economico_relatorio_oc", ["fornecedor"])
    op.create_index("ix_economico_relatorio_oc_data", "economico_relatorio_oc", ["data"])
    op.create_index("ix_economico_relatorio_oc_conta", "economico_relatorio_oc", ["conta"])

    op.create_table(
        "economico_analise_dre",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("importacao_id", sa.Integer(), nullable=False),
        sa.Column("categoria", sa.String(), nullable=False),
        sa.Column("projetado", sa.Float(), nullable=True),
        sa.Column("razao", sa.Float(), nullable=True),
        sa.Column("asocnf", sa.Float(), nullable=True),
        sa.Column("fat_nao_lancado_razao", sa.Float(), nullable=True),
        sa.Column("forecast", sa.Float(), nullable=True),
        sa.Column("previsao_anterior", sa.Float(), nullable=True),
        sa.Column("considerar", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["importacao_id"], ["economico_importacao.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_economico_analise_dre_importacao_id", "economico_analise_dre", ["importacao_id"])
    op.create_index("ix_economico_analise_dre_categoria", "economico_analise_dre", ["categoria"])

    op.create_table(
        "economico_conta_despesa",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("importacao_id", sa.Integer(), nullable=False),
        sa.Column("conta", sa.String(), nullable=False),
        sa.Column("descricao", sa.String(), nullable=True),
        sa.Column("comentario", sa.Text(), nullable=True),
        sa.Column("agrupamento_dre", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["importacao_id"], ["economico_importacao.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_economico_conta_despesa_importacao_id", "economico_conta_despesa", ["importacao_id"])
    op.create_index("ix_economico_conta_despesa_conta", "economico_conta_despesa", ["conta"])
    op.create_index("ix_economico_conta_despesa_agrupamento_dre", "economico_conta_despesa", ["agrupamento_dre"])


def downgrade():
    op.drop_index("ix_economico_conta_despesa_agrupamento_dre", table_name="economico_conta_despesa")
    op.drop_index("ix_economico_conta_despesa_conta", table_name="economico_conta_despesa")
    op.drop_index("ix_economico_conta_despesa_importacao_id", table_name="economico_conta_despesa")
    op.drop_table("economico_conta_despesa")
    op.drop_index("ix_economico_analise_dre_categoria", table_name="economico_analise_dre")
    op.drop_index("ix_economico_analise_dre_importacao_id", table_name="economico_analise_dre")
    op.drop_table("economico_analise_dre")
    op.drop_index("ix_economico_relatorio_oc_conta", table_name="economico_relatorio_oc")
    op.drop_index("ix_economico_relatorio_oc_data", table_name="economico_relatorio_oc")
    op.drop_index("ix_economico_relatorio_oc_fornecedor", table_name="economico_relatorio_oc")
    op.drop_index("ix_economico_relatorio_oc_numero_oc", table_name="economico_relatorio_oc")
    op.drop_index("ix_economico_relatorio_oc_importacao_id", table_name="economico_relatorio_oc")
    op.drop_table("economico_relatorio_oc")
    op.drop_index("ix_economico_lancamento_razao_categoria_dre", table_name="economico_lancamento_razao")
    op.drop_index("ix_economico_lancamento_razao_conta", table_name="economico_lancamento_razao")
    op.drop_index("ix_economico_lancamento_razao_fornecedor", table_name="economico_lancamento_razao")
    op.drop_index("ix_economico_lancamento_razao_documento", table_name="economico_lancamento_razao")
    op.drop_index("ix_economico_lancamento_razao_data", table_name="economico_lancamento_razao")
    op.drop_index("ix_economico_lancamento_razao_importacao_id", table_name="economico_lancamento_razao")
    op.drop_table("economico_lancamento_razao")
    op.drop_index("ix_economico_resumo_calculado_categoria", table_name="economico_resumo_calculado")
    op.drop_index("ix_economico_resumo_calculado_periodo", table_name="economico_resumo_calculado")
    op.drop_index("ix_economico_resumo_calculado_cenario", table_name="economico_resumo_calculado")
    op.drop_index("ix_economico_resumo_calculado_indicador", table_name="economico_resumo_calculado")
    op.drop_index("ix_economico_resumo_calculado_importacao_id", table_name="economico_resumo_calculado")
    op.drop_table("economico_resumo_calculado")
