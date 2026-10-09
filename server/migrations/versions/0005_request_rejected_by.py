"""request rejected by

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-10 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The requests rejected so far take the person from the journal entry that rejected them. Only the
# author, the moderator and the finance director bring a request to this status, and the author is
# never the moderator of their own request, so whoever is neither was the finance director.
FILL_REJECTED_BY = """
    UPDATE expense_request AS request
    SET rejected_by_id = entry.person_id,
        rejected_as = CASE
            WHEN entry.person_id = request.author_id THEN 'author'
            WHEN entry.person_id = request.moderator_id THEN 'moderator'
            ELSE 'finance_director'
        END
    FROM (
        SELECT DISTINCT ON (request_id) request_id, person_id
        FROM journal_entry
        WHERE status = 'rejected' AND status_changed
        ORDER BY request_id, id DESC
    ) AS entry
    WHERE entry.request_id = request.id AND request.status = 'rejected'
"""


def upgrade() -> None:
    op.add_column("expense_request", sa.Column("rejected_by_id", sa.Integer(), nullable=True))
    op.add_column("expense_request", sa.Column("rejected_as", sa.String(length=16), nullable=True))
    op.create_foreign_key(
        op.f("expense_request_rejected_by_id_fkey"), "expense_request", "person", ["rejected_by_id"], ["id"]
    )
    op.execute(FILL_REJECTED_BY)


def downgrade() -> None:
    op.drop_constraint(op.f("expense_request_rejected_by_id_fkey"), "expense_request", type_="foreignkey")
    op.drop_column("expense_request", "rejected_as")
    op.drop_column("expense_request", "rejected_by_id")
