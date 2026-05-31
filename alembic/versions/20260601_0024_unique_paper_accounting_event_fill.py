"""unique paper accounting event fill

Revision ID: 20260601_0024
Revises: 20260531_0023
Create Date: 2026-06-01 00:00:00.000000
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260601_0024"
down_revision = "20260531_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_paper_accounting_events_fill_id",
        "paper_accounting_events",
        ["fill_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_paper_accounting_events_fill_id",
        "paper_accounting_events",
        type_="unique",
    )
