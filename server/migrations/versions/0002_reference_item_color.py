"""reference item color

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-08 12:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("reference_item", sa.Column("color", sa.String(length=16), nullable=True))


def downgrade() -> None:
    op.drop_column("reference_item", "color")
