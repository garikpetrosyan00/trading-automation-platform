"""allow rsi threshold strategy type

Revision ID: 20260517_0018
Revises: 20260514_0017
Create Date: 2026-05-17 00:00:00
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260517_0018"
down_revision = "20260514_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_strategies_strategy_type", "strategies", type_="check")
    op.create_check_constraint(
        "ck_strategies_strategy_type",
        "strategies",
        "strategy_type IN ('price_threshold', 'moving_average_cross', 'rsi_threshold')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_strategies_strategy_type", "strategies", type_="check")
    op.create_check_constraint(
        "ck_strategies_strategy_type",
        "strategies",
        "strategy_type IN ('price_threshold', 'moving_average_cross')",
    )
