"""extend paper execution records

Revision ID: 20260526_0021
Revises: 20260518_0020
Create Date: 2026-05-26 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260526_0021"
down_revision = "20260518_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("simulated_orders") as batch_op:
        batch_op.drop_constraint("ck_simulated_orders_status", type_="check")
        batch_op.add_column(sa.Column("bot_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("strategy_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("order_type", sa.String(length=20), server_default="market", nullable=False)
        )
        batch_op.add_column(sa.Column("mode", sa.String(length=20), server_default="paper", nullable=False))
        batch_op.add_column(sa.Column("decision_reason", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("metadata", sa.JSON(), nullable=True))
        batch_op.add_column(
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)
        )
        batch_op.create_foreign_key(
            "fk_simulated_orders_bot_id_bots",
            "bots",
            ["bot_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_simulated_orders_strategy_id_strategies",
            "strategies",
            ["strategy_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_check_constraint(
            "ck_simulated_orders_status",
            "status IN ('created', 'submitted', 'filled', 'rejected', 'cancelled')",
        )
        batch_op.create_check_constraint("ck_simulated_orders_mode", "mode IN ('paper', 'live')")
        batch_op.create_check_constraint("ck_simulated_orders_order_type", "order_type IN ('market')")

    op.create_index(op.f("ix_simulated_orders_bot_id"), "simulated_orders", ["bot_id"], unique=False)
    op.create_index(op.f("ix_simulated_orders_strategy_id"), "simulated_orders", ["strategy_id"], unique=False)
    op.create_index(op.f("ix_simulated_orders_mode"), "simulated_orders", ["mode"], unique=False)

    with op.batch_alter_table("simulated_fills") as batch_op:
        batch_op.add_column(sa.Column("fill_quantity", sa.Numeric(precision=18, scale=8), nullable=True))
        batch_op.add_column(sa.Column("source", sa.String(length=20), server_default="paper", nullable=False))
        batch_op.add_column(
            sa.Column("filled_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True)
        )

    op.execute("UPDATE simulated_fills SET fill_quantity = quantity WHERE fill_quantity IS NULL")
    op.execute("UPDATE simulated_fills SET filled_at = created_at WHERE filled_at IS NULL")

    with op.batch_alter_table("simulated_fills") as batch_op:
        batch_op.alter_column("fill_quantity", existing_type=sa.Numeric(precision=18, scale=8), nullable=False)
        batch_op.alter_column("filled_at", existing_type=sa.DateTime(timezone=True), nullable=False)

    op.create_index(op.f("ix_simulated_fills_source"), "simulated_fills", ["source"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_simulated_fills_source"), table_name="simulated_fills")
    with op.batch_alter_table("simulated_fills") as batch_op:
        batch_op.drop_column("filled_at")
        batch_op.drop_column("source")
        batch_op.drop_column("fill_quantity")

    op.drop_index(op.f("ix_simulated_orders_mode"), table_name="simulated_orders")
    op.drop_index(op.f("ix_simulated_orders_strategy_id"), table_name="simulated_orders")
    op.drop_index(op.f("ix_simulated_orders_bot_id"), table_name="simulated_orders")
    with op.batch_alter_table("simulated_orders") as batch_op:
        batch_op.drop_constraint("ck_simulated_orders_order_type", type_="check")
        batch_op.drop_constraint("ck_simulated_orders_mode", type_="check")
        batch_op.drop_constraint("ck_simulated_orders_status", type_="check")
        batch_op.drop_constraint("fk_simulated_orders_strategy_id_strategies", type_="foreignkey")
        batch_op.drop_constraint("fk_simulated_orders_bot_id_bots", type_="foreignkey")
        batch_op.drop_column("updated_at")
        batch_op.drop_column("metadata")
        batch_op.drop_column("decision_reason")
        batch_op.drop_column("mode")
        batch_op.drop_column("order_type")
        batch_op.drop_column("strategy_id")
        batch_op.drop_column("bot_id")
        batch_op.create_check_constraint("ck_simulated_orders_status", "status IN ('filled', 'rejected')")
