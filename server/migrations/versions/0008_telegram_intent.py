"""telegram intent

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-10 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "telegram_intent",
        sa.Column("token", sa.String(length=32), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=True),
        sa.Column("question_message_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(["person_id"], ["person.id"]),
        sa.ForeignKeyConstraint(["request_id"], ["expense_request.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )
    op.create_index(op.f("ix_telegram_intent_person_id"), "telegram_intent", ["person_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_telegram_intent_person_id"), table_name="telegram_intent")
    op.drop_table("telegram_intent")
