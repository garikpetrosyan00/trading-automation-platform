"""add bot cooldown seconds

Revision ID: 20260421_0010
Revises: 20260421_0009
Create Date: 2026-04-21 00:40:24.200704
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260421_0010"
down_revision = "20260421_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "execution_profiles",
        sa.Column("cooldown_seconds", sa.Integer(), server_default="60", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("execution_profiles", "cooldown_seconds")
