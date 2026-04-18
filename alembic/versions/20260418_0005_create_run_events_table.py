"""create run events table

Revision ID: 20260418_0005
Revises: 20260418_0004
Create Date: 2026-04-18 02:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260418_0005"
down_revision = "20260418_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "run_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bot_run_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=20), nullable=False),
        sa.Column("level", sa.String(length=20), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('lifecycle', 'log', 'system', 'error')",
            name="ck_run_events_event_type",
        ),
        sa.CheckConstraint(
            "level IN ('info', 'warning', 'error')",
            name="ck_run_events_level",
        ),
        sa.ForeignKeyConstraint(["bot_run_id"], ["bot_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_run_events_bot_run_id"), "run_events", ["bot_run_id"], unique=False)
    op.create_index(op.f("ix_run_events_created_at"), "run_events", ["created_at"], unique=False)
    op.create_index(op.f("ix_run_events_event_type"), "run_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_run_events_id"), "run_events", ["id"], unique=False)
    op.create_index(op.f("ix_run_events_level"), "run_events", ["level"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_run_events_level"), table_name="run_events")
    op.drop_index(op.f("ix_run_events_id"), table_name="run_events")
    op.drop_index(op.f("ix_run_events_event_type"), table_name="run_events")
    op.drop_index(op.f("ix_run_events_created_at"), table_name="run_events")
    op.drop_index(op.f("ix_run_events_bot_run_id"), table_name="run_events")
    op.drop_table("run_events")
