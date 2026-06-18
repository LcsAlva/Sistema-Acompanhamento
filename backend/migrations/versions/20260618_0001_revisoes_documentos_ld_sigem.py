"""Gestao de revisoes LD/SIGEM e impacto em controles.

Revision ID: r1e2v3d4o618
Revises: f2o3p4m5v607
Create Date: 2026-06-18 16:45:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect


revision = "r1e2v3d4o618"
down_revision = "f2o3p4m5v607"
branch_labels = None
depends_on = None


def _table_exists(conn, table: str) -> bool:
    return table in sa_inspect(conn).get_table_names()


def upgrade() -> None:
    conn = op.get_bind()

    if not _table_exists(conn, "documento_revisoes"):
        op.create_table(
            "documento_revisoes",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("codigo_documento", sa.String(), nullable=False),
            sa.Column("revisao", sa.String(), nullable=False),
            sa.Column("revisao_vigente", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("status_documento", sa.String(), server_default="Vigente"),
            sa.Column("status_classificacao", sa.String(), server_default="Pendente de classificacao"),
            sa.Column("data_recebimento", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("origem", sa.String(), server_default="Manual"),
            sa.Column("arquivo", sa.String()),
            sa.Column("observacao_revisao", sa.Text()),
            sa.Column("substitui_revisao", sa.String()),
            sa.Column("criado_em", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("atualizado_em", sa.DateTime(), server_default=sa.func.now()),
            sa.UniqueConstraint("codigo_documento", "revisao", name="uq_documento_revisoes_codigo_revisao"),
        )
        op.create_index("ix_documento_revisoes_codigo_documento", "documento_revisoes", ["codigo_documento"])
        op.create_index("ix_documento_revisoes_revisao_vigente", "documento_revisoes", ["revisao_vigente"])
        op.create_index("ix_documento_revisoes_status_documento", "documento_revisoes", ["status_documento"])
        op.create_index("ix_documento_revisoes_status_classificacao", "documento_revisoes", ["status_classificacao"])
        op.create_index("ix_documento_revisoes_data_recebimento", "documento_revisoes", ["data_recebimento"])
        op.create_index("ix_documento_revisoes_origem", "documento_revisoes", ["origem"])

    if not _table_exists(conn, "controles_documento"):
        op.create_table(
            "controles_documento",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("codigo_controle", sa.String(), nullable=False),
            sa.Column("documento_origem", sa.String(), nullable=False),
            sa.Column("revisao_documento", sa.String()),
            sa.Column("controle_aplicavel", sa.String()),
            sa.Column("status_controle", sa.String(), server_default="Aberto"),
            sa.Column("tem_pedido", sa.Boolean(), server_default=sa.false()),
            sa.Column("numero_pedido", sa.String()),
            sa.Column("status_pedido", sa.String()),
            sa.Column("revisao_documento_usada", sa.String()),
            sa.Column("data_pedido", sa.Date()),
            sa.Column("tem_material", sa.Boolean(), server_default=sa.false()),
            sa.Column("tem_montagem", sa.Boolean(), server_default=sa.false()),
            sa.Column("entrou_medicao_report", sa.Boolean(), server_default=sa.false()),
            sa.Column("criado_em", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("atualizado_em", sa.DateTime(), server_default=sa.func.now()),
            sa.UniqueConstraint("codigo_controle", name="uq_controles_documento_codigo"),
        )
        op.create_index("ix_controles_documento_codigo_controle", "controles_documento", ["codigo_controle"])
        op.create_index("ix_controles_documento_documento_origem", "controles_documento", ["documento_origem"])
        op.create_index("ix_controles_documento_status_controle", "controles_documento", ["status_controle"])

    if not _table_exists(conn, "eventos_revisao_documento"):
        op.create_table(
            "eventos_revisao_documento",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("id_evento_revisao", sa.String(), nullable=False),
            sa.Column("codigo_documento", sa.String(), nullable=False),
            sa.Column("revisao_anterior", sa.String()),
            sa.Column("revisao_nova", sa.String(), nullable=False),
            sa.Column("data_deteccao", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("controles_afetados", sa.Text()),
            sa.Column("status_analise", sa.String(), server_default="Pendente analise"),
            sa.Column("analisado_por", sa.String()),
            sa.Column("data_analise", sa.DateTime()),
            sa.Column("impacto_quantitativo", sa.Boolean(), server_default=sa.false()),
            sa.Column("impacto_material", sa.Boolean(), server_default=sa.false()),
            sa.Column("impacto_montagem", sa.Boolean(), server_default=sa.false()),
            sa.Column("impacto_medicao_report", sa.Boolean(), server_default=sa.false()),
            sa.Column("impacto_informado", sa.String()),
            sa.Column("acao_necessaria", sa.String()),
            sa.Column("observacao_impacto", sa.Text()),
            sa.Column("item_controlavel", sa.String()),
            sa.Column("quantidade_anterior", sa.Float()),
            sa.Column("quantidade_nova", sa.Float()),
            sa.Column("diferenca_quantidade", sa.Float()),
            sa.Column("unidade", sa.String()),
            sa.Column("tipo_variacao", sa.String()),
            sa.Column("acao_pedido", sa.String()),
            sa.Column("criado_em", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("atualizado_em", sa.DateTime(), server_default=sa.func.now()),
            sa.UniqueConstraint("id_evento_revisao", name="uq_eventos_revisao_id_evento"),
        )
        op.create_index("ix_eventos_revisao_documento_id_evento_revisao", "eventos_revisao_documento", ["id_evento_revisao"])
        op.create_index("ix_eventos_revisao_documento_codigo_documento", "eventos_revisao_documento", ["codigo_documento"])
        op.create_index("ix_eventos_revisao_documento_data_deteccao", "eventos_revisao_documento", ["data_deteccao"])
        op.create_index("ix_eventos_revisao_documento_status_analise", "eventos_revisao_documento", ["status_analise"])


def downgrade() -> None:
    op.drop_index("ix_eventos_revisao_documento_status_analise", table_name="eventos_revisao_documento")
    op.drop_index("ix_eventos_revisao_documento_data_deteccao", table_name="eventos_revisao_documento")
    op.drop_index("ix_eventos_revisao_documento_codigo_documento", table_name="eventos_revisao_documento")
    op.drop_index("ix_eventos_revisao_documento_id_evento_revisao", table_name="eventos_revisao_documento")
    op.drop_table("eventos_revisao_documento")

    op.drop_index("ix_controles_documento_status_controle", table_name="controles_documento")
    op.drop_index("ix_controles_documento_documento_origem", table_name="controles_documento")
    op.drop_index("ix_controles_documento_codigo_controle", table_name="controles_documento")
    op.drop_table("controles_documento")

    op.drop_index("ix_documento_revisoes_origem", table_name="documento_revisoes")
    op.drop_index("ix_documento_revisoes_data_recebimento", table_name="documento_revisoes")
    op.drop_index("ix_documento_revisoes_status_classificacao", table_name="documento_revisoes")
    op.drop_index("ix_documento_revisoes_status_documento", table_name="documento_revisoes")
    op.drop_index("ix_documento_revisoes_revisao_vigente", table_name="documento_revisoes")
    op.drop_index("ix_documento_revisoes_codigo_documento", table_name="documento_revisoes")
    op.drop_table("documento_revisoes")
