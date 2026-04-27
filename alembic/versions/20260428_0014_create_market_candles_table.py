"""create market candles table

Revision ID: 20260428_0014
Revises: 20260428_0013
Create Date: 2026-04-28 00:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260428_0014"
down_revision = "20260428_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "market_candles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=50), nullable=False),
        sa.Column("timeframe", sa.String(length=50), nullable=False),
        sa.Column("open_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("close_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open_price", sa.Numeric(18, 8), nullable=False),
        sa.Column("high_price", sa.Numeric(18, 8), nullable=False),
        sa.Column("low_price", sa.Numeric(18, 8), nullable=False),
        sa.Column("close_price", sa.Numeric(18, 8), nullable=False),
        sa.Column("volume", sa.Numeric(28, 8), nullable=False),
        sa.Column("source", sa.String(length=50), server_default="manual", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("open_price > 0", name="ck_market_candles_open_price_positive"),
        sa.CheckConstraint("high_price > 0", name="ck_market_candles_high_price_positive"),
        sa.CheckConstraint("low_price > 0", name="ck_market_candles_low_price_positive"),
        sa.CheckConstraint("close_price > 0", name="ck_market_candles_close_price_positive"),
        sa.CheckConstraint("volume >= 0", name="ck_market_candles_volume_non_negative"),
        sa.CheckConstraint("close_time >= open_time", name="ck_market_candles_close_time_after_open_time"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "symbol",
            "timeframe",
            "open_time",
            "source",
            name="uq_market_candles_symbol_timeframe_open_time_source",
        ),
    )
    op.create_index(op.f("ix_market_candles_id"), "market_candles", ["id"], unique=False)
    op.create_index(op.f("ix_market_candles_symbol"), "market_candles", ["symbol"], unique=False)
    op.create_index(op.f("ix_market_candles_timeframe"), "market_candles", ["timeframe"], unique=False)
    op.create_index(op.f("ix_market_candles_open_time"), "market_candles", ["open_time"], unique=False)
    op.create_index(
        "ix_market_candles_symbol_timeframe_open_time",
        "market_candles",
        ["symbol", "timeframe", "open_time"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_market_candles_symbol_timeframe_open_time", table_name="market_candles")
    op.drop_index(op.f("ix_market_candles_open_time"), table_name="market_candles")
    op.drop_index(op.f("ix_market_candles_timeframe"), table_name="market_candles")
    op.drop_index(op.f("ix_market_candles_symbol"), table_name="market_candles")
    op.drop_index(op.f("ix_market_candles_id"), table_name="market_candles")
    op.drop_table("market_candles")
