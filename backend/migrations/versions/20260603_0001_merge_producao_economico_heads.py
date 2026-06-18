"""Merge Producao and Economico/Performance migration heads.

Revision ID: m1a2b3c4d606
Revises: b7c8d9e10305, p2a3b4c5d605
Create Date: 2026-06-03
"""

from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401


revision = "m1a2b3c4d606"
down_revision = ("b7c8d9e10305", "p2a3b4c5d605")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
