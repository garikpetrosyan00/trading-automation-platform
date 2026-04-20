"""create portfolio simulation tables

Revision ID: 20260421_0008
Revises: 20260419_0007
Create Date: 2026-04-21 00:06:47.573566
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260421_0008"
down_revision = "20260419_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "portfolio_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("base_currency", sa.String(length=10), nullable=False),
        sa.Column("starting_cash", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("cash_balance", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_portfolio_accounts_id"), "portfolio_accounts", ["id"], unique=False)

    op.create_table(
        "positions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=50), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("average_entry_price", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol"),
    )
    op.create_index(op.f("ix_positions_id"), "positions", ["id"], unique=False)
    op.create_index(op.f("ix_positions_symbol"), "positions", ["symbol"], unique=True)

    op.create_table(
        "simulated_orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=50), nullable=False),
        sa.Column("side", sa.String(length=10), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("requested_price_snapshot", sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("rejection_reason", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("side IN ('buy', 'sell')", name="ck_simulated_orders_side"),
        sa.CheckConstraint("status IN ('filled', 'rejected')", name="ck_simulated_orders_status"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_simulated_orders_created_at"), "simulated_orders", ["created_at"], unique=False)
    op.create_index(op.f("ix_simulated_orders_id"), "simulated_orders", ["id"], unique=False)
    op.create_index(op.f("ix_simulated_orders_side"), "simulated_orders", ["side"], unique=False)
    op.create_index(op.f("ix_simulated_orders_status"), "simulated_orders", ["status"], unique=False)
    op.create_index(op.f("ix_simulated_orders_symbol"), "simulated_orders", ["symbol"], unique=False)

    op.create_table(
        "simulated_fills",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=50), nullable=False),
        sa.Column("side", sa.String(length=10), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("fill_price", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("fee", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["simulated_orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_simulated_fills_id"), "simulated_fills", ["id"], unique=False)
    op.create_index(op.f("ix_simulated_fills_order_id"), "simulated_fills", ["order_id"], unique=False)
    op.create_index(op.f("ix_simulated_fills_side"), "simulated_fills", ["side"], unique=False)
    op.create_index(op.f("ix_simulated_fills_symbol"), "simulated_fills", ["symbol"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_simulated_fills_symbol"), table_name="simulated_fills")
    op.drop_index(op.f("ix_simulated_fills_side"), table_name="simulated_fills")
    op.drop_index(op.f("ix_simulated_fills_order_id"), table_name="simulated_fills")
    op.drop_index(op.f("ix_simulated_fills_id"), table_name="simulated_fills")
    op.drop_table("simulated_fills")

    op.drop_index(op.f("ix_simulated_orders_symbol"), table_name="simulated_orders")
    op.drop_index(op.f("ix_simulated_orders_status"), table_name="simulated_orders")
    op.drop_index(op.f("ix_simulated_orders_side"), table_name="simulated_orders")
    op.drop_index(op.f("ix_simulated_orders_id"), table_name="simulated_orders")
    op.drop_index(op.f("ix_simulated_orders_created_at"), table_name="simulated_orders")
    op.drop_table("simulated_orders")

    op.drop_index(op.f("ix_positions_symbol"), table_name="positions")
    op.drop_index(op.f("ix_positions_id"), table_name="positions")
    op.drop_table("positions")

    op.drop_index(op.f("ix_portfolio_accounts_id"), table_name="portfolio_accounts")
    op.drop_table("portfolio_accounts")
