"""add strategy parameters

Revision ID: 20260427_0011
Revises: 20260421_0010
Create Date: 2026-04-27 00:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260427_0011"
down_revision = "20260421_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "strategies",
        sa.Column("parameters", sa.JSON(), server_default="{}", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("strategies", "parameters")
