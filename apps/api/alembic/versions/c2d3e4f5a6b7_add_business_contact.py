"""add business contact fields to users

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-05-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = [
    ("business_email", sa.String(320)),
    ("business_phone", sa.String(40)),
    ("business_address_line1", sa.String(200)),
    ("business_address_line2", sa.String(200)),
    ("business_city", sa.String(120)),
    ("business_postal_code", sa.String(10)),
]


def upgrade() -> None:
    for name, type_ in _COLUMNS:
        op.add_column("users", sa.Column(name, type_, nullable=True))


def downgrade() -> None:
    for name, _ in reversed(_COLUMNS):
        op.drop_column("users", name)
