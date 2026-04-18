"""create execution profiles table

Revision ID: 20260418_0003
Revises: 20260418_0002
Create Date: 2026-04-18 01:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260418_0003"
down_revision = "20260418_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "execution_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bot_id", sa.Integer(), nullable=False),
        sa.Column("max_position_size_usd", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("max_daily_loss_usd", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("max_open_positions", sa.Integer(), nullable=False),
        sa.Column("default_order_type", sa.String(length=20), server_default="limit", nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "default_order_type IN ('market', 'limit')",
            name="ck_execution_profiles_default_order_type",
        ),
        sa.ForeignKeyConstraint(["bot_id"], ["bots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_execution_profiles_bot_id"), "execution_profiles", ["bot_id"], unique=True)
    op.create_index(op.f("ix_execution_profiles_id"), "execution_profiles", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_execution_profiles_id"), table_name="execution_profiles")
    op.drop_index(op.f("ix_execution_profiles_bot_id"), table_name="execution_profiles")
    op.drop_table("execution_profiles")
