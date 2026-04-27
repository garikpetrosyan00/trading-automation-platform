"""allow moving average cross strategy type

Revision ID: 20260428_0013
Revises: 20260427_0012
Create Date: 2026-04-28 00:00:00
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260428_0013"
down_revision = "20260427_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_strategies_strategy_type", "strategies", type_="check")
    op.create_check_constraint(
        "ck_strategies_strategy_type",
        "strategies",
        "strategy_type IN ('price_threshold', 'moving_average_cross')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_strategies_strategy_type", "strategies", type_="check")
    op.create_check_constraint(
        "ck_strategies_strategy_type",
        "strategies",
        "strategy_type IN ('price_threshold')",
    )
