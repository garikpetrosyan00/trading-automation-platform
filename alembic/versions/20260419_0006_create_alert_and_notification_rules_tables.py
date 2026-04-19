"""create alert and notification rules tables

Revision ID: 20260419_0006
Revises: 20260418_0005
Create Date: 2026-04-19 10:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260419_0006"
down_revision = "20260418_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alert_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bot_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("field_name", sa.String(length=100), nullable=False),
        sa.Column("operator", sa.String(length=20), nullable=False),
        sa.Column("threshold_value", sa.String(length=255), nullable=False),
        sa.Column("severity", sa.String(length=20), server_default="warning", nullable=False),
        sa.Column("cooldown_seconds", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "operator IN ('gt', 'gte', 'lt', 'lte', 'eq', 'neq', 'contains')",
            name="ck_alert_rules_operator",
        ),
        sa.CheckConstraint(
            "severity IN ('info', 'warning', 'critical')",
            name="ck_alert_rules_severity",
        ),
        sa.ForeignKeyConstraint(["bot_id"], ["bots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bot_id", "name", name="uq_alert_rules_bot_id_name"),
    )
    op.create_index(op.f("ix_alert_rules_bot_id"), "alert_rules", ["bot_id"], unique=False)
    op.create_index(op.f("ix_alert_rules_id"), "alert_rules", ["id"], unique=False)

    op.create_table(
        "notification_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("alert_rule_id", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("target", sa.String(length=255), nullable=False),
        sa.Column("message_template", sa.Text(), nullable=True),
        sa.Column("send_on_resolved", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("throttle_seconds", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "channel IN ('telegram', 'email', 'webhook', 'log')",
            name="ck_notification_rules_channel",
        ),
        sa.ForeignKeyConstraint(["alert_rule_id"], ["alert_rules.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "alert_rule_id",
            "channel",
            "target",
            name="uq_notification_rules_alert_rule_id_channel_target",
        ),
    )
    op.create_index(op.f("ix_notification_rules_alert_rule_id"), "notification_rules", ["alert_rule_id"], unique=False)
    op.create_index(op.f("ix_notification_rules_id"), "notification_rules", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_notification_rules_id"), table_name="notification_rules")
    op.drop_index(op.f("ix_notification_rules_alert_rule_id"), table_name="notification_rules")
    op.drop_table("notification_rules")
    op.drop_index(op.f("ix_alert_rules_id"), table_name="alert_rules")
    op.drop_index(op.f("ix_alert_rules_bot_id"), table_name="alert_rules")
    op.drop_table("alert_rules")
