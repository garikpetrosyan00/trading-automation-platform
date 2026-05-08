"""create backtest runs table

Revision ID: 20260509_0015
Revises: 20260428_0014
Create Date: 2026-05-09 00:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260509_0015"
down_revision = "20260428_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("strategy_id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=50), nullable=False),
        sa.Column("timeframe", sa.String(length=50), nullable=False),
        sa.Column("strategy_type", sa.String(length=50), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=True),
        sa.Column("initial_balance", sa.Numeric(28, 8), nullable=False),
        sa.Column("final_balance", sa.Numeric(28, 8), nullable=False),
        sa.Column("cash_balance", sa.Numeric(28, 8), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(28, 8), nullable=False),
        sa.Column("unrealized_pnl", sa.Numeric(28, 8), nullable=False),
        sa.Column("number_of_trades", sa.Integer(), nullable=False),
        sa.Column("closed_trades", sa.Integer(), nullable=False),
        sa.Column("open_position", sa.Boolean(), nullable=False),
        sa.Column("position_quantity", sa.Numeric(28, 8), nullable=False),
        sa.Column("entry_price", sa.Numeric(18, 8), nullable=True),
        sa.Column("winning_trades", sa.Integer(), nullable=False),
        sa.Column("losing_trades", sa.Integer(), nullable=False),
        sa.Column("candles_processed", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_backtest_runs_id"), "backtest_runs", ["id"], unique=False)
    op.create_index(op.f("ix_backtest_runs_strategy_id"), "backtest_runs", ["strategy_id"], unique=False)
    op.create_index(op.f("ix_backtest_runs_symbol"), "backtest_runs", ["symbol"], unique=False)
    op.create_index(
        "ix_backtest_runs_strategy_id_created_at",
        "backtest_runs",
        ["strategy_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_backtest_runs_strategy_id_created_at", table_name="backtest_runs")
    op.drop_index(op.f("ix_backtest_runs_symbol"), table_name="backtest_runs")
    op.drop_index(op.f("ix_backtest_runs_strategy_id"), table_name="backtest_runs")
    op.drop_index(op.f("ix_backtest_runs_id"), table_name="backtest_runs")
    op.drop_table("backtest_runs")
