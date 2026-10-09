"""journal entry payer

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-10 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The entries written so far changed no payer.
    op.add_column("journal_entry", sa.Column("payer_changed", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("journal_entry", sa.Column("payer_id", sa.Integer(), nullable=True))
    op.create_foreign_key(op.f("journal_entry_payer_id_fkey"), "journal_entry", "person", ["payer_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint(op.f("journal_entry_payer_id_fkey"), "journal_entry", type_="foreignkey")
    op.drop_column("journal_entry", "payer_id")
    op.drop_column("journal_entry", "payer_changed")
