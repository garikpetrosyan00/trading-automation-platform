"""create execution reconciliation jobs table

Revision ID: 20260608_0027
Revises: 20260605_0026
Create Date: 2026-06-08 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260608_0027"
down_revision = "20260605_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "execution_reconciliation_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("execution_attempt_id", sa.Integer(), nullable=False),
        sa.Column("bot_id", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_token", sa.String(length=64), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("automatic_attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_resolution", sa.String(length=50), nullable=True),
        sa.Column("last_failure_category", sa.String(length=50), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "state IN ('pending', 'claimed', 'resolved', 'exhausted')",
            name="ck_execution_reconciliation_jobs_state",
        ),
        sa.CheckConstraint(
            "automatic_attempt_count >= 0",
            name="ck_execution_reconciliation_jobs_attempt_count_non_negative",
        ),
        sa.ForeignKeyConstraint(["bot_id"], ["bots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["execution_attempt_id"], ["execution_attempts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("execution_attempt_id", name="uq_execution_reconciliation_jobs_attempt"),
    )
    op.create_index(op.f("ix_execution_reconciliation_jobs_id"), "execution_reconciliation_jobs", ["id"], unique=False)
    op.create_index(
        op.f("ix_execution_reconciliation_jobs_execution_attempt_id"),
        "execution_reconciliation_jobs",
        ["execution_attempt_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_execution_reconciliation_jobs_bot_id"),
        "execution_reconciliation_jobs",
        ["bot_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_execution_reconciliation_jobs_state"),
        "execution_reconciliation_jobs",
        ["state"],
        unique=False,
    )
    op.create_index(
        op.f("ix_execution_reconciliation_jobs_next_attempt_at"),
        "execution_reconciliation_jobs",
        ["next_attempt_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_execution_reconciliation_jobs_lease_expires_at"),
        "execution_reconciliation_jobs",
        ["lease_expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_execution_reconciliation_jobs_state_next_attempt_at",
        "execution_reconciliation_jobs",
        ["state", "next_attempt_at"],
        unique=False,
    )
    op.create_index(
        "ix_execution_reconciliation_jobs_state_lease_expires_at",
        "execution_reconciliation_jobs",
        ["state", "lease_expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_execution_reconciliation_jobs_state_lease_expires_at", table_name="execution_reconciliation_jobs")
    op.drop_index("ix_execution_reconciliation_jobs_state_next_attempt_at", table_name="execution_reconciliation_jobs")
    op.drop_index(op.f("ix_execution_reconciliation_jobs_lease_expires_at"), table_name="execution_reconciliation_jobs")
    op.drop_index(op.f("ix_execution_reconciliation_jobs_next_attempt_at"), table_name="execution_reconciliation_jobs")
    op.drop_index(op.f("ix_execution_reconciliation_jobs_state"), table_name="execution_reconciliation_jobs")
    op.drop_index(op.f("ix_execution_reconciliation_jobs_bot_id"), table_name="execution_reconciliation_jobs")
    op.drop_index(
        op.f("ix_execution_reconciliation_jobs_execution_attempt_id"),
        table_name="execution_reconciliation_jobs",
    )
    op.drop_index(op.f("ix_execution_reconciliation_jobs_id"), table_name="execution_reconciliation_jobs")
    op.drop_table("execution_reconciliation_jobs")
