"""create draft balances table

Revision ID: 20260616_0029
Revises: 20260613_0028
Create Date: 2026-06-16 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260616_0029"
down_revision = "20260613_0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "draft_balances",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bot_id", sa.Integer(), nullable=False),
        sa.Column("asset", sa.String(length=20), nullable=False),
        sa.Column("available", sa.Numeric(18, 8), server_default="0", nullable=False),
        sa.Column("locked", sa.Numeric(18, 8), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("available >= 0", name="ck_draft_balances_available_non_negative"),
        sa.CheckConstraint("locked >= 0", name="ck_draft_balances_locked_non_negative"),
        sa.ForeignKeyConstraint(["bot_id"], ["bots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bot_id", "asset", name="uq_draft_balances_bot_asset"),
    )
    op.create_index(op.f("ix_draft_balances_id"), "draft_balances", ["id"], unique=False)
    op.create_index(op.f("ix_draft_balances_bot_id"), "draft_balances", ["bot_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_draft_balances_bot_id"), table_name="draft_balances")
    op.drop_index(op.f("ix_draft_balances_id"), table_name="draft_balances")
    op.drop_table("draft_balances")
