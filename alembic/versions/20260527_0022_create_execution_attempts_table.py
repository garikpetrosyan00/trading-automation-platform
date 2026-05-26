"""create execution attempts table

Revision ID: 20260527_0022
Revises: 20260526_0021
Create Date: 2026-05-27 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260527_0022"
down_revision = "20260526_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "execution_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bot_id", sa.Integer(), nullable=True),
        sa.Column("strategy_id", sa.Integer(), nullable=True),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("symbol", sa.String(length=50), nullable=False),
        sa.Column("side", sa.String(length=10), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("broker", sa.String(length=50), nullable=True),
        sa.Column("requested_quantity", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("requested_price", sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column("decision_reason", sa.String(length=255), nullable=True),
        sa.Column("risk_status", sa.String(length=50), nullable=True),
        sa.Column("safety_status", sa.String(length=50), nullable=True),
        sa.Column("final_status", sa.String(length=50), nullable=False),
        sa.Column("final_reason", sa.String(length=255), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("side IN ('buy', 'sell')", name="ck_execution_attempts_side"),
        sa.CheckConstraint("mode IN ('paper', 'testnet', 'live')", name="ck_execution_attempts_mode"),
        sa.CheckConstraint(
            "final_status IN ("
            "'created', "
            "'blocked_by_risk', "
            "'blocked_by_safety', "
            "'rejected_by_broker', "
            "'order_created', "
            "'filled', "
            "'failed'"
            ")",
            name="ck_execution_attempts_final_status",
        ),
        sa.ForeignKeyConstraint(["bot_id"], ["bots.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["order_id"], ["simulated_orders.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategies.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_execution_attempts_id"), "execution_attempts", ["id"], unique=False)
    op.create_index(op.f("ix_execution_attempts_bot_id"), "execution_attempts", ["bot_id"], unique=False)
    op.create_index(op.f("ix_execution_attempts_strategy_id"), "execution_attempts", ["strategy_id"], unique=False)
    op.create_index(op.f("ix_execution_attempts_order_id"), "execution_attempts", ["order_id"], unique=False)
    op.create_index(op.f("ix_execution_attempts_symbol"), "execution_attempts", ["symbol"], unique=False)
    op.create_index(op.f("ix_execution_attempts_side"), "execution_attempts", ["side"], unique=False)
    op.create_index(op.f("ix_execution_attempts_mode"), "execution_attempts", ["mode"], unique=False)
    op.create_index(op.f("ix_execution_attempts_broker"), "execution_attempts", ["broker"], unique=False)
    op.create_index(op.f("ix_execution_attempts_risk_status"), "execution_attempts", ["risk_status"], unique=False)
    op.create_index(op.f("ix_execution_attempts_safety_status"), "execution_attempts", ["safety_status"], unique=False)
    op.create_index(op.f("ix_execution_attempts_final_status"), "execution_attempts", ["final_status"], unique=False)
    op.create_index(op.f("ix_execution_attempts_created_at"), "execution_attempts", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_execution_attempts_created_at"), table_name="execution_attempts")
    op.drop_index(op.f("ix_execution_attempts_final_status"), table_name="execution_attempts")
    op.drop_index(op.f("ix_execution_attempts_safety_status"), table_name="execution_attempts")
    op.drop_index(op.f("ix_execution_attempts_risk_status"), table_name="execution_attempts")
    op.drop_index(op.f("ix_execution_attempts_broker"), table_name="execution_attempts")
    op.drop_index(op.f("ix_execution_attempts_mode"), table_name="execution_attempts")
    op.drop_index(op.f("ix_execution_attempts_side"), table_name="execution_attempts")
    op.drop_index(op.f("ix_execution_attempts_symbol"), table_name="execution_attempts")
    op.drop_index(op.f("ix_execution_attempts_order_id"), table_name="execution_attempts")
    op.drop_index(op.f("ix_execution_attempts_strategy_id"), table_name="execution_attempts")
    op.drop_index(op.f("ix_execution_attempts_bot_id"), table_name="execution_attempts")
    op.drop_index(op.f("ix_execution_attempts_id"), table_name="execution_attempts")
    op.drop_table("execution_attempts")
