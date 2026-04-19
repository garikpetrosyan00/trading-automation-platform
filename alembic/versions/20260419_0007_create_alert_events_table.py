"""create alert events table

Revision ID: 20260419_0007
Revises: 20260419_0006
Create Date: 2026-04-19 12:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260419_0007"
down_revision = "20260419_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alert_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bot_id", sa.Integer(), nullable=False),
        sa.Column("bot_run_id", sa.Integer(), nullable=True),
        sa.Column("alert_rule_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="triggered", nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("field_name", sa.String(length=100), nullable=False),
        sa.Column("operator", sa.String(length=20), nullable=False),
        sa.Column("threshold_value", sa.String(length=255), nullable=False),
        sa.Column("actual_value", sa.Text(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("dedup_key", sa.String(length=255), nullable=True),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('triggered', 'resolved', 'suppressed')",
            name="ck_alert_events_status",
        ),
        sa.ForeignKeyConstraint(["alert_rule_id"], ["alert_rules.id"]),
        sa.ForeignKeyConstraint(["bot_id"], ["bots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["bot_run_id"], ["bot_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_alert_events_alert_rule_id"), "alert_events", ["alert_rule_id"], unique=False)
    op.create_index(op.f("ix_alert_events_bot_id"), "alert_events", ["bot_id"], unique=False)
    op.create_index(op.f("ix_alert_events_bot_run_id"), "alert_events", ["bot_run_id"], unique=False)
    op.create_index(op.f("ix_alert_events_dedup_key"), "alert_events", ["dedup_key"], unique=False)
    op.create_index(op.f("ix_alert_events_id"), "alert_events", ["id"], unique=False)
    op.create_index(op.f("ix_alert_events_status"), "alert_events", ["status"], unique=False)
    op.create_index(op.f("ix_alert_events_triggered_at"), "alert_events", ["triggered_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_alert_events_triggered_at"), table_name="alert_events")
    op.drop_index(op.f("ix_alert_events_status"), table_name="alert_events")
    op.drop_index(op.f("ix_alert_events_id"), table_name="alert_events")
    op.drop_index(op.f("ix_alert_events_dedup_key"), table_name="alert_events")
    op.drop_index(op.f("ix_alert_events_bot_run_id"), table_name="alert_events")
    op.drop_index(op.f("ix_alert_events_bot_id"), table_name="alert_events")
    op.drop_index(op.f("ix_alert_events_alert_rule_id"), table_name="alert_events")
    op.drop_table("alert_events")
