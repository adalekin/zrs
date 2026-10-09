"""recurrence and payments

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-10 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# A request paid so far has one payment: by its payer, on its payment date, of its own amount.
# No other amount was recorded.
FILL_PAYMENTS = """
    INSERT INTO payment (request_id, person_id, paid_on, amount)
    SELECT id, payer_id, paid_on, amount
    FROM expense_request
    WHERE status = 'paid' AND payer_id IS NOT NULL AND paid_on IS NOT NULL
    ORDER BY id
"""


def upgrade() -> None:
    op.add_column("expense_request", sa.Column("recurrence", sa.String(length=16), nullable=True))
    # The recurrence says how often to pay; the words about the period are a note the author may leave out.
    op.alter_column("expense_request", "payment_period", existing_type=sa.String(length=255), nullable=True)
    op.create_table(
        "payment",
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("paid_on", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(["person_id"], ["person.id"]),
        sa.ForeignKeyConstraint(["request_id"], ["expense_request.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_payment_request_id"), "payment", ["request_id"], unique=False)
    op.execute(FILL_PAYMENTS)


def downgrade() -> None:
    op.drop_index(op.f("ix_payment_request_id"), table_name="payment")
    op.drop_table("payment")
    op.execute("UPDATE expense_request SET payment_period = '' WHERE payment_period IS NULL")
    op.alter_column("expense_request", "payment_period", existing_type=sa.String(length=255), nullable=False)
    op.drop_column("expense_request", "recurrence")
