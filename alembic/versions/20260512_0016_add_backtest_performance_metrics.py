"""add backtest performance metrics

Revision ID: 20260512_0016
Revises: 20260509_0015
Create Date: 2026-05-12 00:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260512_0016"
down_revision = "20260509_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("backtest_runs", sa.Column("total_return", sa.Numeric(28, 8), nullable=True))
    op.add_column("backtest_runs", sa.Column("total_return_percent", sa.Numeric(28, 8), nullable=True))
    op.add_column("backtest_runs", sa.Column("win_rate", sa.Numeric(28, 8), nullable=True))
    op.add_column("backtest_runs", sa.Column("average_trade_pnl", sa.Numeric(28, 8), nullable=True))
    op.add_column("backtest_runs", sa.Column("best_trade_pnl", sa.Numeric(28, 8), nullable=True))
    op.add_column("backtest_runs", sa.Column("worst_trade_pnl", sa.Numeric(28, 8), nullable=True))
    op.add_column("backtest_runs", sa.Column("profit_factor", sa.Numeric(28, 8), nullable=True))


def downgrade() -> None:
    op.drop_column("backtest_runs", "profit_factor")
    op.drop_column("backtest_runs", "worst_trade_pnl")
    op.drop_column("backtest_runs", "best_trade_pnl")
    op.drop_column("backtest_runs", "average_trade_pnl")
    op.drop_column("backtest_runs", "win_rate")
    op.drop_column("backtest_runs", "total_return_percent")
    op.drop_column("backtest_runs", "total_return")
