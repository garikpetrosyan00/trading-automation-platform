"""add execution profile risk limits

Revision ID: 20260514_0017
Revises: 20260512_0016
Create Date: 2026-05-14 00:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260514_0017"
down_revision = "20260512_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("execution_profiles", sa.Column("max_trade_quantity", sa.Numeric(18, 8), nullable=True))
    op.add_column("execution_profiles", sa.Column("max_position_quantity", sa.Numeric(18, 8), nullable=True))
    op.add_column("execution_profiles", sa.Column("stop_loss_percent", sa.Numeric(18, 8), nullable=True))


def downgrade() -> None:
    op.drop_column("execution_profiles", "stop_loss_percent")
    op.drop_column("execution_profiles", "max_position_quantity")
    op.drop_column("execution_profiles", "max_trade_quantity")
