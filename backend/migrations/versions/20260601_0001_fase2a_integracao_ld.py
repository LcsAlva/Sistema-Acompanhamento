"""Fase 2A — Sistema de Medição Petrobras (Integração LD/SIGEM + Critérios)

Cria as 3 tabelas-base da Fase 2A:
  - criterios_medicao    (Módulo 3 — matriz de critérios parametrizável)
  - ld_documentos        (Módulo 1 — Lista de Documentos da S5 / status SIGEM)
  - ld_historico_status  (Módulo 1 — histórico de transições de status)

Aditiva: não altera nenhuma tabela existente (BM/EAP/Documentos intactos).

Revision ID: c3d4e5f60201
Revises: a1b2c3d4e506
Create Date: 2026-06-01 00:01:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect


revision = 'c3d4e5f60201'
down_revision = 'a1b2c3d4e506'
branch_labels = None
depends_on = None


def _table_exists(conn, table: str) -> bool:
    return table in sa_inspect(conn).get_table_names()


def upgrade() -> None:
    conn = op.get_bind()
    if all(_table_exists(conn, table) for table in ('criterios_medicao', 'ld_documentos', 'ld_historico_status')):
        return

    # ── Módulo 3 — Matriz de Critérios ───────────────────────────────────
    op.create_table(
        'criterios_medicao',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('codigo_eap', sa.String(), nullable=False),
        sa.Column('descricao', sa.String()),
        sa.Column('tipo_criterio', sa.String(), nullable=False, server_default='MANUAL'),
        sa.Column('peso', sa.Float(), server_default='1.0'),
        sa.Column('evidencia_obrigatoria', sa.Boolean(), server_default=sa.false()),
        sa.Column('ativo', sa.Boolean(), server_default=sa.true()),
        sa.Column('parametros', sa.Text()),
        sa.Column('criado_em', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('atualizado_em', sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint('codigo_eap', name='uq_criterios_codigo_eap'),
    )
    op.create_index('ix_criterios_medicao_codigo_eap', 'criterios_medicao', ['codigo_eap'])
    op.create_index('ix_criterios_medicao_tipo_criterio', 'criterios_medicao', ['tipo_criterio'])

    # ── Módulo 1 — Lista de Documentos (LD/SIGEM) ────────────────────────
    op.create_table(
        'ld_documentos',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('codigo_documento', sa.String(), nullable=False),
        sa.Column('titulo', sa.String()),
        sa.Column('disciplina', sa.String()),
        sa.Column('revisao', sa.String()),
        sa.Column('status', sa.String()),
        sa.Column('a4_equivalente', sa.Float(), server_default='0.0'),
        sa.Column('data_prevista', sa.Date()),
        sa.Column('data_emissao', sa.Date()),
        sa.Column('data_importacao', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('origem_arquivo', sa.String()),
        sa.UniqueConstraint('codigo_documento', name='uq_ld_documentos_codigo'),
    )
    op.create_index('ix_ld_documentos_codigo_documento', 'ld_documentos', ['codigo_documento'])
    op.create_index('ix_ld_documentos_disciplina', 'ld_documentos', ['disciplina'])
    op.create_index('ix_ld_documentos_status', 'ld_documentos', ['status'])

    op.create_table(
        'ld_historico_status',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('documento_id', sa.Integer(), nullable=False),
        sa.Column('status_anterior', sa.String()),
        sa.Column('status_novo', sa.String()),
        sa.Column('data_alteracao', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('arquivo_origem', sa.String()),
        sa.ForeignKeyConstraint(['documento_id'], ['ld_documentos.id'], name='fk_ld_hist_documento'),
    )
    op.create_index('ix_ld_historico_status_documento_id', 'ld_historico_status', ['documento_id'])
    op.create_index('ix_ld_historico_status_data_alteracao', 'ld_historico_status', ['data_alteracao'])


def downgrade() -> None:
    op.drop_index('ix_ld_historico_status_data_alteracao', table_name='ld_historico_status')
    op.drop_index('ix_ld_historico_status_documento_id', table_name='ld_historico_status')
    op.drop_table('ld_historico_status')

    op.drop_index('ix_ld_documentos_status', table_name='ld_documentos')
    op.drop_index('ix_ld_documentos_disciplina', table_name='ld_documentos')
    op.drop_index('ix_ld_documentos_codigo_documento', table_name='ld_documentos')
    op.drop_table('ld_documentos')

    op.drop_index('ix_criterios_medicao_tipo_criterio', table_name='criterios_medicao')
    op.drop_index('ix_criterios_medicao_codigo_eap', table_name='criterios_medicao')
    op.drop_table('criterios_medicao')
