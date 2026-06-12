"""create execution reconciliation worker status table

Revision ID: 20260613_0028
Revises: 20260608_0027
Create Date: 2026-06-13 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260613_0028"
down_revision = "20260608_0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "execution_reconciliation_worker_status",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("worker_name", sa.String(length=80), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("last_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_cycle_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_cycle_finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_cycle_result_code", sa.String(length=50), nullable=True),
        sa.Column("last_processed_reconciliation_job_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "state IN ('running', 'stopped')",
            name="ck_execution_reconciliation_worker_status_state",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("worker_name", name="uq_execution_reconciliation_worker_status_worker_name"),
    )
    op.create_index(
        op.f("ix_execution_reconciliation_worker_status_id"),
        "execution_reconciliation_worker_status",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_execution_reconciliation_worker_status_worker_name",
        "execution_reconciliation_worker_status",
        ["worker_name"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_execution_reconciliation_worker_status_worker_name", table_name="execution_reconciliation_worker_status")
    op.drop_index(op.f("ix_execution_reconciliation_worker_status_id"), table_name="execution_reconciliation_worker_status")
    op.drop_table("execution_reconciliation_worker_status")
