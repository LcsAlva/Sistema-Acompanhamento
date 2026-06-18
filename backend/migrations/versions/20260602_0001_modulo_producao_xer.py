"""Modulo Producao — cronograma XER (Primavera P6).

Cria tabelas aditivas:
  - prod_projeto
  - prod_wbs
  - prod_atividade

Revision ID: f5a6b7c80103
Revises: e4f5a6b7c802
Create Date: 2026-06-02 10:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect


revision = 'f5a6b7c80103'
down_revision = 'e4f5a6b7c802'
branch_labels = None
depends_on = None


def _table_exists(conn, table: str) -> bool:
    return table in sa_inspect(conn).get_table_names()


def upgrade() -> None:
    conn = op.get_bind()
    if all(_table_exists(conn, table) for table in ('prod_projeto', 'prod_wbs', 'prod_atividade')):
        return

    op.create_table(
        'prod_projeto',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('proj_short_name', sa.String()),
        sa.Column('data_date', sa.Date()),
        sa.Column('plan_start', sa.Date()),
        sa.Column('plan_end', sa.Date()),
        sa.Column('origem_arquivo', sa.String()),
        sa.Column('total_atividades', sa.Integer(), server_default='0'),
        sa.Column('importado_em', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('ativo', sa.Boolean(), server_default=sa.true()),
    )
    op.create_index('ix_prod_projeto_data_date', 'prod_projeto', ['data_date'])
    op.create_index('ix_prod_projeto_ativo', 'prod_projeto', ['ativo'])

    op.create_table(
        'prod_wbs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('projeto_id', sa.Integer(), sa.ForeignKey('prod_projeto.id'), nullable=False),
        sa.Column('wbs_uid', sa.String()),
        sa.Column('parent_uid', sa.String()),
        sa.Column('short_name', sa.String()),
        sa.Column('nome', sa.String()),
        sa.Column('is_node', sa.Boolean(), server_default=sa.false()),
    )
    op.create_index('ix_prod_wbs_projeto_id', 'prod_wbs', ['projeto_id'])
    op.create_index('ix_prod_wbs_wbs_uid', 'prod_wbs', ['wbs_uid'])
    op.create_index('ix_prod_wbs_parent_uid', 'prod_wbs', ['parent_uid'])

    op.create_table(
        'prod_atividade',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('projeto_id', sa.Integer(), sa.ForeignKey('prod_projeto.id'), nullable=False),
        sa.Column('task_code', sa.String()),
        sa.Column('nome', sa.String()),
        sa.Column('wbs_uid', sa.String()),
        sa.Column('wbs_nome', sa.String()),
        sa.Column('disciplina', sa.String()),
        sa.Column('fase', sa.String()),
        sa.Column('area', sa.String()),
        sa.Column('status', sa.String()),
        sa.Column('phys_pct', sa.Float(), server_default='0'),
        sa.Column('peso', sa.Float(), server_default='0'),
        sa.Column('target_start', sa.Date()),
        sa.Column('target_end', sa.Date()),
        sa.Column('act_start', sa.Date()),
        sa.Column('act_end', sa.Date()),
        sa.Column('total_float_hr', sa.Float()),
        sa.Column('critica', sa.Boolean(), server_default=sa.false()),
        sa.Column('is_marco', sa.Boolean(), server_default=sa.false()),
        sa.Column('responsavel', sa.String()),
    )
    op.create_index('ix_prod_atividade_projeto_id', 'prod_atividade', ['projeto_id'])
    op.create_index('ix_prod_atividade_task_code', 'prod_atividade', ['task_code'])
    op.create_index('ix_prod_atividade_disciplina', 'prod_atividade', ['disciplina'])
    op.create_index('ix_prod_atividade_fase', 'prod_atividade', ['fase'])
    op.create_index('ix_prod_atividade_target_end', 'prod_atividade', ['target_end'])
    op.create_index('ix_prod_atividade_critica', 'prod_atividade', ['critica'])
    op.create_index('ix_prod_atividade_is_marco', 'prod_atividade', ['is_marco'])
    op.create_index('ix_prod_atividade_status', 'prod_atividade', ['status'])


def downgrade() -> None:
    op.drop_table('prod_atividade')
    op.drop_table('prod_wbs')
    op.drop_table('prod_projeto')
