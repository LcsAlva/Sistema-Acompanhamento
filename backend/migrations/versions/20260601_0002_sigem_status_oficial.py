"""SIGEM como fonte oficial de status da medicao.

Cria tabelas aditivas:
  - sigem_documentos
  - sigem_historico_status

Revision ID: e4f5a6b7c802
Revises: c3d4e5f60201
Create Date: 2026-06-01 09:30:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect


revision = 'e4f5a6b7c802'
down_revision = 'c3d4e5f60201'
branch_labels = None
depends_on = None


def _table_exists(conn, table: str) -> bool:
    return table in sa_inspect(conn).get_table_names()


def upgrade() -> None:
    conn = op.get_bind()
    if _table_exists(conn, 'sigem_documentos') and _table_exists(conn, 'sigem_historico_status'):
        return

    op.create_table(
        'sigem_documentos',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('codigo_documento', sa.String(), nullable=False),
        sa.Column('revisao', sa.String()),
        sa.Column('status', sa.String()),
        sa.Column('modificado_em', sa.DateTime()),
        sa.Column('incluido_em', sa.DateTime()),
        sa.Column('nivel_1', sa.String()),
        sa.Column('nivel_2', sa.String()),
        sa.Column('nivel_3', sa.String()),
        sa.Column('nivel_4', sa.String()),
        sa.Column('nivel_5', sa.String()),
        sa.Column('nivel_6', sa.String()),
        sa.Column('nivel_7', sa.String()),
        sa.Column('nivel_8', sa.String()),
        sa.Column('origem_arquivo', sa.String()),
        sa.Column('data_importacao', sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint('codigo_documento', name='uq_sigem_documentos_codigo'),
    )
    op.create_index('ix_sigem_documentos_codigo_documento', 'sigem_documentos', ['codigo_documento'])
    op.create_index('ix_sigem_documentos_status', 'sigem_documentos', ['status'])

    op.create_table(
        'sigem_historico_status',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('documento_id', sa.Integer(), nullable=False),
        sa.Column('status_anterior', sa.String()),
        sa.Column('status_novo', sa.String()),
        sa.Column('data_alteracao', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('arquivo_origem', sa.String()),
        sa.ForeignKeyConstraint(['documento_id'], ['sigem_documentos.id'], name='fk_sigem_hist_documento'),
    )
    op.create_index('ix_sigem_historico_status_documento_id', 'sigem_historico_status', ['documento_id'])
    op.create_index('ix_sigem_historico_status_data_alteracao', 'sigem_historico_status', ['data_alteracao'])


def downgrade() -> None:
    op.drop_index('ix_sigem_historico_status_data_alteracao', table_name='sigem_historico_status')
    op.drop_index('ix_sigem_historico_status_documento_id', table_name='sigem_historico_status')
    op.drop_table('sigem_historico_status')

    op.drop_index('ix_sigem_documentos_status', table_name='sigem_documentos')
    op.drop_index('ix_sigem_documentos_codigo_documento', table_name='sigem_documentos')
    op.drop_table('sigem_documentos')
