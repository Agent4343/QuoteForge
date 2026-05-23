"""add users.labor_cost_rate_cad

Revision ID: b1c2d3e4f5a6
Revises: a46a6eaa3652
Create Date: 2026-05-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "a46a6eaa3652"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "labor_cost_rate_cad",
            sa.Numeric(8, 2),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "labor_cost_rate_cad")
