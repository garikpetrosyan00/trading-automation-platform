"""create paper positions

Revision ID: 20260618_0030
Revises: 20260616_0029
Create Date: 2026-06-18 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260618_0030"
down_revision = "20260616_0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "paper_positions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bot_id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=50), nullable=False),
        sa.Column("base_asset", sa.String(length=20), nullable=False),
        sa.Column("quote_asset", sa.String(length=20), nullable=False),
        sa.Column("quantity", sa.Numeric(28, 8), server_default="0", nullable=False),
        sa.Column("average_entry_price", sa.Numeric(28, 8), server_default="0", nullable=False),
        sa.Column("realized_pnl", sa.Numeric(28, 8), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("quantity >= 0", name="ck_paper_positions_quantity_non_negative"),
        sa.ForeignKeyConstraint(["bot_id"], ["bots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bot_id", "symbol", name="uq_paper_positions_bot_symbol"),
    )
    op.create_index(op.f("ix_paper_positions_id"), "paper_positions", ["id"], unique=False)
    op.create_index(op.f("ix_paper_positions_bot_id"), "paper_positions", ["bot_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_paper_positions_bot_id"), table_name="paper_positions")
    op.drop_index(op.f("ix_paper_positions_id"), table_name="paper_positions")
    op.drop_table("paper_positions")
