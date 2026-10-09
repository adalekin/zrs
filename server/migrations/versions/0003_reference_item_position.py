"""reference item position

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-09 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("reference_item", sa.Column("position", sa.Integer(), nullable=True))
    # Only priorities have an order. They start in the order the list has shown them so far, by name.
    op.execute(
        """
        UPDATE reference_item
        SET position = ranked.place
        FROM (
            SELECT id, row_number() OVER (ORDER BY name) AS place
            FROM reference_item
            WHERE kind = 'priority'
        ) AS ranked
        WHERE reference_item.id = ranked.id
        """
    )


def downgrade() -> None:
    op.drop_column("reference_item", "position")
