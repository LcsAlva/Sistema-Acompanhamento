"""Formaliza tabelas do módulo BM (eram criadas em _migrate() no main.py).

Também adiciona colunas de eap_previsao_mensal e tarefas que foram
adicionadas via ALTER TABLE ad-hoc em main.py mas não estavam no Alembic.

Usa CREATE TABLE IF NOT EXISTS e add_column condicional para ser
idempotente em bancos pré-existentes.

Revision ID: c3a1b2d4e501
Revises: 075cfb9d4358
Create Date: 2026-05-21 00:01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = 'c3a1b2d4e501'
down_revision = '075cfb9d4358'
branch_labels = None
depends_on = None


def _col_exists(conn, table: str, col: str) -> bool:
    insp = sa_inspect(conn)
    return col in {c['name'] for c in insp.get_columns(table)}


def _table_exists(conn, table: str) -> bool:
    insp = sa_inspect(conn)
    return table in insp.get_table_names()


def upgrade() -> None:
    conn = op.get_bind()

    # ── Colunas ad-hoc de tarefas ─────────────────────────────────────────
    with op.batch_alter_table('tarefas') as batch:
        if not _col_exists(conn, 'tarefas', 'wbs_path'):
            batch.add_column(sa.Column('wbs_path', sa.Text(), nullable=True))
        if not _col_exists(conn, 'tarefas', 'pct_avanco'):
            batch.add_column(sa.Column('pct_avanco', sa.Float(), server_default='0.0'))
        if not _col_exists(conn, 'tarefas', 'unid_orcadas_smo'):
            batch.add_column(sa.Column('unid_orcadas_smo', sa.Float(), nullable=True))

    # ── Colunas ad-hoc de eap_previsao_mensal ────────────────────────────
    with op.batch_alter_table('eap_previsao_mensal') as batch:
        if not _col_exists(conn, 'eap_previsao_mensal', 'adiantada'):
            batch.add_column(sa.Column('adiantada', sa.Boolean(), server_default='0'))
        if not _col_exists(conn, 'eap_previsao_mensal', 'mes_original_ano'):
            batch.add_column(sa.Column('mes_original_ano', sa.Integer(), nullable=True))
        if not _col_exists(conn, 'eap_previsao_mensal', 'mes_original_mes'):
            batch.add_column(sa.Column('mes_original_mes', sa.Integer(), nullable=True))

    # ── Tabelas BM (IF NOT EXISTS para idempotência) ──────────────────────
    if not _table_exists(conn, 'bm_ciclo'):
        op.create_table(
            'bm_ciclo',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('ano', sa.Integer(), nullable=False),
            sa.Column('mes', sa.Integer(), nullable=False),
            sa.Column('status', sa.String(), nullable=False, server_default='em_previa'),
            sa.Column('numero_bm', sa.String(), nullable=True),
            sa.Column('ciclo_legado_id', sa.Integer(),
                      sa.ForeignKey('ciclo_medicao.id'), nullable=True),
            sa.Column('criado_em', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('criado_por', sa.String(), nullable=True),
            sa.Column('enviado_analise_em', sa.DateTime(), nullable=True),
            sa.Column('enviado_analise_por', sa.String(), nullable=True),
            sa.Column('pre_aprovado_em', sa.DateTime(), nullable=True),
            sa.Column('pre_aprovado_por', sa.String(), nullable=True),
            sa.Column('fechado_em', sa.DateTime(), nullable=True),
            sa.Column('fechado_por', sa.String(), nullable=True),
            sa.Column('consolidado_em', sa.DateTime(), nullable=True),
            sa.Column('consolidado_por', sa.String(), nullable=True),
            sa.Column('observacao', sa.Text(), nullable=True),
            sa.UniqueConstraint('ano', 'mes', name='uq_bm_ciclo_ano_mes'),
        )
        op.create_index('ix_bm_ciclo_status', 'bm_ciclo', ['status'])
        op.create_index('ix_bm_ciclo_ano', 'bm_ciclo', ['ano'])
        op.create_index('ix_bm_ciclo_mes', 'bm_ciclo', ['mes'])
        op.create_index('ix_bm_ciclo_ano_mes', 'bm_ciclo', ['ano', 'mes'])

    if not _table_exists(conn, 'bm_snapshot_previsao'):
        op.create_table(
            'bm_snapshot_previsao',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('ciclo_id', sa.Integer(),
                      sa.ForeignKey('bm_ciclo.id'), nullable=False),
            sa.Column('eap_codigo', sa.String(),
                      sa.ForeignKey('eap_item.codigo'), nullable=False),
            sa.Column('pct_previsto', sa.Float(), nullable=False, server_default='0.0'),
            sa.Column('adiantada', sa.Boolean(), server_default='0'),
            sa.Column('mes_origem_ano', sa.Integer(), nullable=True),
            sa.Column('mes_origem_mes', sa.Integer(), nullable=True),
            sa.Column('observacao', sa.Text(), nullable=True),
            sa.Column('capturado_em', sa.DateTime(), server_default=sa.func.now()),
            sa.UniqueConstraint('ciclo_id', 'eap_codigo', name='uq_bm_snap_ciclo_eap'),
        )
        op.create_index('ix_bm_snap_ciclo', 'bm_snapshot_previsao', ['ciclo_id'])
        op.create_index('ix_bm_snap_eap', 'bm_snapshot_previsao', ['eap_codigo'])

    if not _table_exists(conn, 'bm_lancamento'):
        op.create_table(
            'bm_lancamento',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('ciclo_id', sa.Integer(),
                      sa.ForeignKey('bm_ciclo.id'), nullable=False),
            sa.Column('eap_codigo', sa.String(),
                      sa.ForeignKey('eap_item.codigo'), nullable=False),
            sa.Column('pct_acumulado', sa.Float(), nullable=False, server_default='0.0'),
            sa.Column('observacao', sa.Text(), nullable=True),
            sa.Column('atualizado_em', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('atualizado_por', sa.String(), nullable=True),
            sa.UniqueConstraint('ciclo_id', 'eap_codigo', name='uq_bm_lanc_ciclo_eap'),
        )
        op.create_index('ix_bm_lancamento_ciclo', 'bm_lancamento', ['ciclo_id'])

    if not _table_exists(conn, 'bm_versao'):
        op.create_table(
            'bm_versao',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('ciclo_id', sa.Integer(),
                      sa.ForeignKey('bm_ciclo.id'), nullable=False),
            sa.Column('numero_versao', sa.Integer(), nullable=False),
            sa.Column('status_no_momento', sa.String(), nullable=True),
            sa.Column('lancamentos_json', sa.Text(), nullable=False),
            sa.Column('total_valor_periodo', sa.Float(), server_default='0.0'),
            sa.Column('pct_acum_projeto', sa.Float(), server_default='0.0'),
            sa.Column('criado_em', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('criado_por', sa.String(), nullable=True),
            sa.UniqueConstraint('ciclo_id', 'numero_versao', name='uq_bm_versao_ciclo_num'),
        )

    if not _table_exists(conn, 'bm_consolidado'):
        op.create_table(
            'bm_consolidado',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('ciclo_id', sa.Integer(),
                      sa.ForeignKey('bm_ciclo.id'), nullable=False),
            sa.Column('eap_codigo', sa.String(),
                      sa.ForeignKey('eap_item.codigo'), nullable=False),
            sa.Column('pct_acumulado', sa.Float(), nullable=False, server_default='0.0'),
            sa.Column('pct_periodo', sa.Float(), nullable=False, server_default='0.0'),
            sa.Column('pct_previsto', sa.Float(), nullable=False, server_default='0.0'),
            sa.Column('valor_item', sa.Float(), server_default='0.0'),
            sa.Column('valor_periodo', sa.Float(), server_default='0.0'),
            sa.Column('valor_acumulado', sa.Float(), server_default='0.0'),
            sa.Column('is_folha', sa.Boolean(), server_default='1'),
            sa.Column('nivel', sa.Integer(), server_default='1'),
            sa.Column('criado_em', sa.DateTime(), server_default=sa.func.now()),
            sa.UniqueConstraint('ciclo_id', 'eap_codigo', name='uq_bm_consol_ciclo_eap'),
        )
        op.create_index('ix_bm_consolidado_ciclo', 'bm_consolidado', ['ciclo_id'])
        op.create_index('ix_bm_consolidado_eap', 'bm_consolidado', ['eap_codigo'])

    if not _table_exists(conn, 'bm_pendencia'):
        op.create_table(
            'bm_pendencia',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('ciclo_id', sa.Integer(),
                      sa.ForeignKey('bm_ciclo.id'), nullable=False),
            sa.Column('eap_codigo', sa.String(),
                      sa.ForeignKey('eap_item.codigo'), nullable=False),
            sa.Column('pct_previsto', sa.Float(), nullable=False),
            sa.Column('pct_realizado', sa.Float(), nullable=False),
            sa.Column('pct_gap', sa.Float(), nullable=False),
            sa.Column('valor_item', sa.Float(), server_default='0.0'),
            sa.Column('valor_gap', sa.Float(), server_default='0.0'),
            sa.Column('status', sa.String(), nullable=False, server_default='ativa'),
            sa.Column('pct_ja_redistribuido', sa.Float(), server_default='0.0'),
            sa.Column('mes_destino_ano', sa.Integer(), nullable=True),
            sa.Column('mes_destino_mes', sa.Integer(), nullable=True),
            sa.Column('observacao', sa.Text(), nullable=True),
            sa.Column('gerado_em', sa.DateTime(), server_default=sa.func.now()),
            sa.UniqueConstraint('ciclo_id', 'eap_codigo', name='uq_bm_pend_ciclo_eap'),
        )
        op.create_index('ix_bm_pendencia_status', 'bm_pendencia', ['status'])
        op.create_index('ix_bm_pendencia_ciclo', 'bm_pendencia', ['ciclo_id'])

    if not _table_exists(conn, 'bm_pendencia_redistrib'):
        op.create_table(
            'bm_pendencia_redistrib',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('pendencia_id', sa.Integer(),
                      sa.ForeignKey('bm_pendencia.id'), nullable=False),
            sa.Column('destino_ano', sa.Integer(), nullable=False),
            sa.Column('destino_mes', sa.Integer(), nullable=False),
            sa.Column('pct_redistribuido', sa.Float(), nullable=False),
            sa.Column('valor_redistribuido', sa.Float(), server_default='0.0'),
            sa.Column('observacao', sa.Text(), nullable=True),
            sa.Column('redistribuido_em', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('redistribuido_por', sa.String(), nullable=True),
        )
        op.create_index('ix_bm_redistrib_pendencia', 'bm_pendencia_redistrib', ['pendencia_id'])


def downgrade() -> None:
    # Downgrade remove apenas o que esta migração criou; colunas ad-hoc
    # de tabelas existentes não são removidas no downgrade (segurança).
    for tbl in ['bm_pendencia_redistrib', 'bm_pendencia', 'bm_consolidado',
                'bm_versao', 'bm_lancamento', 'bm_snapshot_previsao', 'bm_ciclo']:
        conn = op.get_bind()
        if _table_exists(conn, tbl):
            op.drop_table(tbl)
