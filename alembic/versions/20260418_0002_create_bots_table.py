"""create bots table

Revision ID: 20260418_0002
Revises: 20260418_0001
Create Date: 2026-04-18 00:30:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260418_0002"
down_revision = "20260418_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("strategy_id", sa.Integer(), nullable=False),
        sa.Column("exchange_name", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column("is_paper", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('draft', 'active', 'paused')", name="ck_bots_status"),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_bots_exchange_name"), "bots", ["exchange_name"], unique=False)
    op.create_index(op.f("ix_bots_id"), "bots", ["id"], unique=False)
    op.create_index(op.f("ix_bots_name"), "bots", ["name"], unique=False)
    op.create_index(op.f("ix_bots_status"), "bots", ["status"], unique=False)
    op.create_index(op.f("ix_bots_strategy_id"), "bots", ["strategy_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_bots_strategy_id"), table_name="bots")
    op.drop_index(op.f("ix_bots_status"), table_name="bots")
    op.drop_index(op.f("ix_bots_name"), table_name="bots")
    op.drop_index(op.f("ix_bots_id"), table_name="bots")
    op.drop_index(op.f("ix_bots_exchange_name"), table_name="bots")
    op.drop_table("bots")
