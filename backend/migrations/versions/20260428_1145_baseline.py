"""baseline — schema atual antes da adoção do Alembic

Revision ID: 9c7d947b4dbc
Revises:
Create Date: 2026-04-28 11:45:56.546545

Esta é a migração inicial. Bancos pré-existentes (que já tinham todas
as tabelas e colunas via Base.metadata.create_all + as ALTER TABLEs
ad-hoc do main.py) devem ser marcados nesta revisão com:

    alembic stamp head

Bancos novos podem rodar `alembic upgrade head`, que executa esta
migração e cria as tabelas a partir dos models.
"""
from alembic import op
import sqlalchemy as sa

from backend.database import Base
from backend import models  # noqa: F401  — registra os models no metadata


revision = '9c7d947b4dbc'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Cria tudo a partir do metadata, idempotente para bancos novos.
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
