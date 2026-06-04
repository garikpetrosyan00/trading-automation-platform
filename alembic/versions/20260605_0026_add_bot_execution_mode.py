"""add bot execution mode

Revision ID: 20260605_0026
Revises: 20260602_0025
Create Date: 2026-06-05 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260605_0026"
down_revision = "20260602_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "bots",
        sa.Column("execution_mode", sa.String(length=20), server_default="paper", nullable=False),
    )
    op.execute("UPDATE bots SET execution_mode = CASE WHEN is_paper THEN 'paper' ELSE 'live' END")
    op.create_check_constraint(
        "ck_bots_execution_mode",
        "bots",
        "execution_mode IN ('paper', 'testnet', 'live')",
    )
    op.create_index(op.f("ix_bots_execution_mode"), "bots", ["execution_mode"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_bots_execution_mode"), table_name="bots")
    op.drop_constraint("ck_bots_execution_mode", "bots", type_="check")
    op.drop_column("bots", "execution_mode")
