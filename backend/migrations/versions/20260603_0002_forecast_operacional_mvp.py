"""Add Forecast Operacional MVP tables.

Revision ID: f2o3p4m5v607
Revises: m1a2b3c4d606
Create Date: 2026-06-03
"""

from alembic import op
import sqlalchemy as sa


revision = "f2o3p4m5v607"
down_revision = "m1a2b3c4d606"
branch_labels = None
depends_on = None


def _table_exists(bind, name: str) -> bool:
    return sa.inspect(bind).has_table(name)


def _index_exists(bind, table: str, index: str) -> bool:
    return index in {idx["name"] for idx in sa.inspect(bind).get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()

    if not _table_exists(bind, "economico_forecast_versao"):
        op.create_table(
            "economico_forecast_versao",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("importacao_id", sa.Integer(), sa.ForeignKey("economico_importacao.id"), nullable=False),
            sa.Column("codigo", sa.String(), nullable=False, unique=True),
            sa.Column("nome", sa.String(), nullable=False),
            sa.Column("motivo", sa.Text()),
            sa.Column("status", sa.String(), nullable=False, server_default="rascunho"),
            sa.Column("origem", sa.String(), nullable=False, server_default="importacao"),
            sa.Column("versao_base_id", sa.Integer(), sa.ForeignKey("economico_forecast_versao.id")),
            sa.Column("criado_por", sa.String()),
            sa.Column("criado_em", sa.DateTime(), server_default=sa.func.now()),
        )
    for index, column in {
        "ix_economico_forecast_versao_importacao_id": "importacao_id",
        "ix_economico_forecast_versao_codigo": "codigo",
        "ix_economico_forecast_versao_status": "status",
        "ix_economico_forecast_versao_origem": "origem",
        "ix_economico_forecast_versao_versao_base_id": "versao_base_id",
    }.items():
        if not _index_exists(bind, "economico_forecast_versao", index):
            op.create_index(index, "economico_forecast_versao", [column])

    if not _table_exists(bind, "economico_forecast_item"):
        op.create_table(
            "economico_forecast_item",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("versao_id", sa.Integer(), sa.ForeignKey("economico_forecast_versao.id"), nullable=False),
            sa.Column("importacao_id", sa.Integer(), sa.ForeignKey("economico_importacao.id"), nullable=False),
            sa.Column("indicador", sa.String(), nullable=False),
            sa.Column("periodo", sa.Date()),
            sa.Column("categoria", sa.String()),
            sa.Column("valor", sa.Float(), server_default="0"),
            sa.Column("origem", sa.String()),
        )
    for index, column in {
        "ix_economico_forecast_item_versao_id": "versao_id",
        "ix_economico_forecast_item_importacao_id": "importacao_id",
        "ix_economico_forecast_item_indicador": "indicador",
        "ix_economico_forecast_item_periodo": "periodo",
        "ix_economico_forecast_item_categoria": "categoria",
    }.items():
        if not _index_exists(bind, "economico_forecast_item", index):
            op.create_index(index, "economico_forecast_item", [column])

    if not _table_exists(bind, "economico_forecast_ajuste"):
        op.create_table(
            "economico_forecast_ajuste",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("versao_id", sa.Integer(), sa.ForeignKey("economico_forecast_versao.id"), nullable=False),
            sa.Column("item_id", sa.Integer(), sa.ForeignKey("economico_forecast_item.id")),
            sa.Column("categoria", sa.String(), nullable=False),
            sa.Column("valor_anterior", sa.Float(), server_default="0"),
            sa.Column("valor_novo", sa.Float(), server_default="0"),
            sa.Column("diferenca", sa.Float(), server_default="0"),
            sa.Column("justificativa", sa.Text(), nullable=False),
            sa.Column("usuario", sa.String()),
            sa.Column("criado_em", sa.DateTime(), server_default=sa.func.now()),
        )
    for index, column in {
        "ix_economico_forecast_ajuste_versao_id": "versao_id",
        "ix_economico_forecast_ajuste_item_id": "item_id",
        "ix_economico_forecast_ajuste_categoria": "categoria",
    }.items():
        if not _index_exists(bind, "economico_forecast_ajuste", index):
            op.create_index(index, "economico_forecast_ajuste", [column])

    if not _table_exists(bind, "economico_forecast_historico"):
        op.create_table(
            "economico_forecast_historico",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("versao_id", sa.Integer(), sa.ForeignKey("economico_forecast_versao.id"), nullable=False),
            sa.Column("acao", sa.String(), nullable=False),
            sa.Column("descricao", sa.Text()),
            sa.Column("usuario", sa.String()),
            sa.Column("payload", sa.Text()),
            sa.Column("criado_em", sa.DateTime(), server_default=sa.func.now()),
        )
    for index, column in {
        "ix_economico_forecast_historico_versao_id": "versao_id",
        "ix_economico_forecast_historico_acao": "acao",
    }.items():
        if not _index_exists(bind, "economico_forecast_historico", index):
            op.create_index(index, "economico_forecast_historico", [column])


def downgrade() -> None:
    bind = op.get_bind()
    for table in [
        "economico_forecast_historico",
        "economico_forecast_ajuste",
        "economico_forecast_item",
        "economico_forecast_versao",
    ]:
        if _table_exists(bind, table):
            op.drop_table(table)
