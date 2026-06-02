"""create execution daily quota usage table

Revision ID: 20260602_0025
Revises: 20260601_0024
Create Date: 2026-06-02 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260602_0025"
down_revision = "20260601_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "execution_daily_quota_usage",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bot_id", sa.Integer(), nullable=True),
        sa.Column("utc_day", sa.Date(), nullable=False),
        sa.Column("accepted_order_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "accepted_order_count >= 0",
            name="ck_execution_daily_quota_usage_count_non_negative",
        ),
        sa.ForeignKeyConstraint(["bot_id"], ["bots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bot_id", "utc_day", name="uq_execution_daily_quota_usage_bot_day"),
    )
    op.create_index(op.f("ix_execution_daily_quota_usage_id"), "execution_daily_quota_usage", ["id"], unique=False)
    op.create_index(
        op.f("ix_execution_daily_quota_usage_bot_id"),
        "execution_daily_quota_usage",
        ["bot_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_execution_daily_quota_usage_utc_day"),
        "execution_daily_quota_usage",
        ["utc_day"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_execution_daily_quota_usage_utc_day"), table_name="execution_daily_quota_usage")
    op.drop_index(op.f("ix_execution_daily_quota_usage_bot_id"), table_name="execution_daily_quota_usage")
    op.drop_index(op.f("ix_execution_daily_quota_usage_id"), table_name="execution_daily_quota_usage")
    op.drop_table("execution_daily_quota_usage")
