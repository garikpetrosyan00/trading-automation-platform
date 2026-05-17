"""allow macd crossover strategy type

Revision ID: 20260518_0020
Revises: 20260518_0019
Create Date: 2026-05-18 00:00:00
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260518_0020"
down_revision = "20260518_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_strategies_strategy_type", "strategies", type_="check")
    op.create_check_constraint(
        "ck_strategies_strategy_type",
        "strategies",
        (
            "strategy_type IN ("
            "'price_threshold', 'moving_average_cross', 'rsi_threshold', "
            "'bollinger_bands', 'macd_crossover'"
            ")"
        ),
    )


def downgrade() -> None:
    op.drop_constraint("ck_strategies_strategy_type", "strategies", type_="check")
    op.create_check_constraint(
        "ck_strategies_strategy_type",
        "strategies",
        "strategy_type IN ('price_threshold', 'moving_average_cross', 'rsi_threshold', 'bollinger_bands')",
    )
