"""add strategy type

Revision ID: 20260427_0012
Revises: 20260427_0011
Create Date: 2026-04-27 00:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260427_0012"
down_revision = "20260427_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "strategies",
        sa.Column("strategy_type", sa.String(length=50), server_default="price_threshold", nullable=False),
    )
    op.create_check_constraint(
        "ck_strategies_strategy_type",
        "strategies",
        "strategy_type IN ('price_threshold')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_strategies_strategy_type", "strategies", type_="check")
    op.drop_column("strategies", "strategy_type")
