"""extend execution profiles for bot runner

Revision ID: 20260421_0009
Revises: 20260421_0008
Create Date: 2026-04-21 00:24:24.314018
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260421_0009"
down_revision = "20260421_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "execution_profiles",
        sa.Column("strategy_type", sa.String(length=50), server_default="price_threshold", nullable=False),
    )
    op.add_column("execution_profiles", sa.Column("entry_below", sa.Numeric(precision=18, scale=8), nullable=True))
    op.add_column("execution_profiles", sa.Column("exit_above", sa.Numeric(precision=18, scale=8), nullable=True))
    op.add_column("execution_profiles", sa.Column("order_quantity", sa.Numeric(precision=18, scale=8), nullable=True))
    op.create_check_constraint(
        "ck_execution_profiles_strategy_type",
        "execution_profiles",
        "strategy_type IN ('price_threshold')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_execution_profiles_strategy_type", "execution_profiles", type_="check")
    op.drop_column("execution_profiles", "order_quantity")
    op.drop_column("execution_profiles", "exit_above")
    op.drop_column("execution_profiles", "entry_below")
    op.drop_column("execution_profiles", "strategy_type")
