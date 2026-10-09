"""notifications

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-10 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "telegram_link",
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(["person_id"], ["person.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("person_id"),
    )
    op.create_index(op.f("ix_telegram_link_chat_id"), "telegram_link", ["chat_id"], unique=False)
    op.create_table(
        "telegram_link_code",
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("used_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(["person_id"], ["person.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "telegram_cursor",
        sa.Column("next_update_id", sa.BigInteger(), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "notification",
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("journal_entry_id", sa.Integer(), nullable=True),
        sa.Column("payment_id", sa.Integer(), nullable=True),
        sa.Column("once_key", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("sent_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("dropped_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(["journal_entry_id"], ["journal_entry.id"]),
        sa.ForeignKeyConstraint(["payment_id"], ["payment.id"]),
        sa.ForeignKeyConstraint(["person_id"], ["person.id"]),
        sa.ForeignKeyConstraint(["request_id"], ["expense_request.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("once_key"),
    )
    # The sender reads the messages that wait, the oldest first.
    op.create_index(
        "ix_notification_waiting",
        "notification",
        ["id"],
        unique=False,
        postgresql_where=sa.text("sent_at IS NULL AND dropped_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_notification_waiting", table_name="notification")
    op.drop_table("notification")
    op.drop_table("telegram_cursor")
    op.drop_table("telegram_link_code")
    op.drop_index(op.f("ix_telegram_link_chat_id"), table_name="telegram_link")
    op.drop_table("telegram_link")
