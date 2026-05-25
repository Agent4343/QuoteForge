"""add users.terms_en / terms_fr

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-05-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d3e4f5a6b7c8"
down_revision: Union[str, None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("terms_en", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("terms_fr", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "terms_fr")
    op.drop_column("users", "terms_en")
