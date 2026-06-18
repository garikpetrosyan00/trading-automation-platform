"""create paper equity snapshots

Revision ID: 20260619_0031
Revises: 20260618_0030
Create Date: 2026-06-19 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260619_0031"
down_revision = "20260618_0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "paper_equity_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bot_id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=50), nullable=False),
        sa.Column("quote_asset", sa.String(length=20), nullable=False),
        sa.Column("cash_available", sa.Numeric(28, 8), nullable=False),
        sa.Column("cash_locked", sa.Numeric(28, 8), nullable=False),
        sa.Column("base_quantity", sa.Numeric(28, 8), nullable=False),
        sa.Column("base_locked", sa.Numeric(28, 8), nullable=False),
        sa.Column("average_entry_price", sa.Numeric(28, 8), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(28, 8), nullable=False),
        sa.Column("market_price", sa.Numeric(28, 8), nullable=True),
        sa.Column("position_value", sa.Numeric(28, 8), nullable=True),
        sa.Column("total_equity", sa.Numeric(28, 8), nullable=True),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("source_order_id", sa.Integer(), nullable=True),
        sa.Column("source_fill_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "base_locked >= 0",
            name="ck_paper_equity_snapshots_base_locked_non_negative",
        ),
        sa.CheckConstraint(
            "base_quantity >= 0",
            name="ck_paper_equity_snapshots_base_quantity_non_negative",
        ),
        sa.CheckConstraint(
            "cash_available >= 0",
            name="ck_paper_equity_snapshots_cash_available_non_negative",
        ),
        sa.CheckConstraint(
            "cash_locked >= 0",
            name="ck_paper_equity_snapshots_cash_locked_non_negative",
        ),
        sa.CheckConstraint(
            "event_type IN ('buy_fill', 'sell_fill', 'reset', 'manual_snapshot')",
            name="ck_paper_equity_snapshots_event_type",
        ),
        sa.ForeignKeyConstraint(["bot_id"], ["bots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_fill_id"], ["simulated_fills.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_order_id"], ["simulated_orders.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_paper_equity_snapshots_bot_id"), "paper_equity_snapshots", ["bot_id"], unique=False)
    op.create_index(op.f("ix_paper_equity_snapshots_created_at"), "paper_equity_snapshots", ["created_at"], unique=False)
    op.create_index(op.f("ix_paper_equity_snapshots_event_type"), "paper_equity_snapshots", ["event_type"], unique=False)
    op.create_index(op.f("ix_paper_equity_snapshots_id"), "paper_equity_snapshots", ["id"], unique=False)
    op.create_index(
        op.f("ix_paper_equity_snapshots_source_fill_id"),
        "paper_equity_snapshots",
        ["source_fill_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_paper_equity_snapshots_source_order_id"),
        "paper_equity_snapshots",
        ["source_order_id"],
        unique=False,
    )
    op.create_index(op.f("ix_paper_equity_snapshots_symbol"), "paper_equity_snapshots", ["symbol"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_paper_equity_snapshots_symbol"), table_name="paper_equity_snapshots")
    op.drop_index(op.f("ix_paper_equity_snapshots_source_order_id"), table_name="paper_equity_snapshots")
    op.drop_index(op.f("ix_paper_equity_snapshots_source_fill_id"), table_name="paper_equity_snapshots")
    op.drop_index(op.f("ix_paper_equity_snapshots_id"), table_name="paper_equity_snapshots")
    op.drop_index(op.f("ix_paper_equity_snapshots_event_type"), table_name="paper_equity_snapshots")
    op.drop_index(op.f("ix_paper_equity_snapshots_created_at"), table_name="paper_equity_snapshots")
    op.drop_index(op.f("ix_paper_equity_snapshots_bot_id"), table_name="paper_equity_snapshots")
    op.drop_table("paper_equity_snapshots")
