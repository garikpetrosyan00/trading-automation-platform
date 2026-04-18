"""create bot runs table

Revision ID: 20260418_0004
Revises: 20260418_0003
Create Date: 2026-04-18 01:30:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260418_0004"
down_revision = "20260418_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bot_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bot_id", sa.Integer(), nullable=False),
        sa.Column("trigger_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="requested", nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "trigger_type IN ('manual', 'scheduled', 'system')",
            name="ck_bot_runs_trigger_type",
        ),
        sa.CheckConstraint(
            "status IN ('requested', 'running', 'succeeded', 'failed', 'cancelled')",
            name="ck_bot_runs_status",
        ),
        sa.ForeignKeyConstraint(["bot_id"], ["bots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_bot_runs_bot_id"), "bot_runs", ["bot_id"], unique=False)
    op.create_index(op.f("ix_bot_runs_created_at"), "bot_runs", ["created_at"], unique=False)
    op.create_index(op.f("ix_bot_runs_id"), "bot_runs", ["id"], unique=False)
    op.create_index(op.f("ix_bot_runs_status"), "bot_runs", ["status"], unique=False)
    op.create_index(op.f("ix_bot_runs_trigger_type"), "bot_runs", ["trigger_type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_bot_runs_trigger_type"), table_name="bot_runs")
    op.drop_index(op.f("ix_bot_runs_status"), table_name="bot_runs")
    op.drop_index(op.f("ix_bot_runs_id"), table_name="bot_runs")
    op.drop_index(op.f("ix_bot_runs_created_at"), table_name="bot_runs")
    op.drop_index(op.f("ix_bot_runs_bot_id"), table_name="bot_runs")
    op.drop_table("bot_runs")
