"""create paper accounting events table

Revision ID: 20260531_0023
Revises: 20260527_0022
Create Date: 2026-05-31 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260531_0023"
down_revision = "20260527_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "paper_accounting_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("fill_id", sa.Integer(), nullable=True),
        sa.Column("bot_id", sa.Integer(), nullable=True),
        sa.Column("strategy_id", sa.Integer(), nullable=True),
        sa.Column("symbol", sa.String(length=50), nullable=False),
        sa.Column("side", sa.String(length=10), nullable=False),
        sa.Column("mode", sa.String(length=20), server_default="paper", nullable=False),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("cash_delta", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("realized_pnl_delta", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("event_type IN ('fill_applied')", name="ck_paper_accounting_events_event_type"),
        sa.CheckConstraint("side IN ('buy', 'sell')", name="ck_paper_accounting_events_side"),
        sa.CheckConstraint("mode = 'paper'", name="ck_paper_accounting_events_mode"),
        sa.ForeignKeyConstraint(["bot_id"], ["bots.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["fill_id"], ["simulated_fills.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["order_id"], ["simulated_orders.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategies.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_paper_accounting_events_id"), "paper_accounting_events", ["id"], unique=False)
    op.create_index(op.f("ix_paper_accounting_events_order_id"), "paper_accounting_events", ["order_id"], unique=False)
    op.create_index(op.f("ix_paper_accounting_events_fill_id"), "paper_accounting_events", ["fill_id"], unique=False)
    op.create_index(op.f("ix_paper_accounting_events_bot_id"), "paper_accounting_events", ["bot_id"], unique=False)
    op.create_index(
        op.f("ix_paper_accounting_events_strategy_id"),
        "paper_accounting_events",
        ["strategy_id"],
        unique=False,
    )
    op.create_index(op.f("ix_paper_accounting_events_symbol"), "paper_accounting_events", ["symbol"], unique=False)
    op.create_index(op.f("ix_paper_accounting_events_side"), "paper_accounting_events", ["side"], unique=False)
    op.create_index(op.f("ix_paper_accounting_events_mode"), "paper_accounting_events", ["mode"], unique=False)
    op.create_index(
        op.f("ix_paper_accounting_events_event_type"),
        "paper_accounting_events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_paper_accounting_events_occurred_at"),
        "paper_accounting_events",
        ["occurred_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_paper_accounting_events_occurred_at"), table_name="paper_accounting_events")
    op.drop_index(op.f("ix_paper_accounting_events_event_type"), table_name="paper_accounting_events")
    op.drop_index(op.f("ix_paper_accounting_events_mode"), table_name="paper_accounting_events")
    op.drop_index(op.f("ix_paper_accounting_events_side"), table_name="paper_accounting_events")
    op.drop_index(op.f("ix_paper_accounting_events_symbol"), table_name="paper_accounting_events")
    op.drop_index(op.f("ix_paper_accounting_events_strategy_id"), table_name="paper_accounting_events")
    op.drop_index(op.f("ix_paper_accounting_events_bot_id"), table_name="paper_accounting_events")
    op.drop_index(op.f("ix_paper_accounting_events_fill_id"), table_name="paper_accounting_events")
    op.drop_index(op.f("ix_paper_accounting_events_order_id"), table_name="paper_accounting_events")
    op.drop_index(op.f("ix_paper_accounting_events_id"), table_name="paper_accounting_events")
    op.drop_table("paper_accounting_events")
