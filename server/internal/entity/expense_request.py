import datetime
from decimal import Decimal

from approck_sqlalchemy_utils.mixins.auto_now import MixinWithAutoNow
from approck_sqlalchemy_utils.model import Base
from sqlalchemy import TIMESTAMP, BigInteger, Boolean, Date, ForeignKey, Numeric, String, Text, false, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from internal.entity.person import Person
from internal.entity.reference_item import ReferenceItem


class ExpenseRequest(MixinWithAutoNow, Base):
    author_id: Mapped[int] = mapped_column(ForeignKey("person.id"), index=True)
    moderator_id: Mapped[int] = mapped_column(ForeignKey("person.id"), index=True)
    payer_id: Mapped[int | None] = mapped_column(ForeignKey("person.id"))

    operation_type_id: Mapped[int] = mapped_column(ForeignKey("reference_item.id"))
    payment_form_id: Mapped[int | None] = mapped_column(ForeignKey("reference_item.id"))
    priority_id: Mapped[int] = mapped_column(ForeignKey("reference_item.id"))

    situation: Mapped[str] = mapped_column(Text)
    solution: Mapped[str] = mapped_column(Text)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    currency: Mapped[str] = mapped_column(String(3))
    payment_period: Mapped[str] = mapped_column(String(255))
    deadline: Mapped[datetime.date | None] = mapped_column(Date)

    status: Mapped[str] = mapped_column(String(16), index=True)
    paid_on: Mapped[datetime.date | None] = mapped_column(Date)

    author: Mapped[Person] = relationship(foreign_keys=[author_id], lazy="joined")
    moderator: Mapped[Person] = relationship(foreign_keys=[moderator_id], lazy="joined")
    payer: Mapped[Person | None] = relationship(foreign_keys=[payer_id], lazy="joined")
    operation_type: Mapped[ReferenceItem] = relationship(foreign_keys=[operation_type_id], lazy="joined")
    payment_form: Mapped[ReferenceItem | None] = relationship(foreign_keys=[payment_form_id], lazy="joined")
    priority: Mapped[ReferenceItem] = relationship(foreign_keys=[priority_id], lazy="joined")
    journal: Mapped[list["JournalEntry"]] = relationship(
        back_populates="request", lazy="selectin", order_by="JournalEntry.id"
    )
    attachments: Mapped[list["Attachment"]] = relationship(
        back_populates="request", lazy="selectin", order_by="Attachment.id"
    )


class JournalEntry(Base):
    """Append-only record of a status change, a change of the payer or a comment. Rows are never updated or deleted."""

    request_id: Mapped[int] = mapped_column(ForeignKey("expense_request.id"), index=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"))
    #: Status of the request right after the action.
    status: Mapped[str] = mapped_column(String(16))
    status_changed: Mapped[bool] = mapped_column(Boolean)
    #: Whether the action changed who pays the request.
    payer_changed: Mapped[bool] = mapped_column(Boolean, server_default=false())
    #: The payer the action gave the request; empty when it took the payer off or left them as they were.
    payer_id: Mapped[int | None] = mapped_column(ForeignKey("person.id"))
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    request: Mapped[ExpenseRequest] = relationship(back_populates="journal")
    person: Mapped[Person] = relationship(foreign_keys=[person_id], lazy="joined")
    payer: Mapped[Person | None] = relationship(foreign_keys=[payer_id], lazy="joined")


class Attachment(Base):
    request_id: Mapped[int] = mapped_column(ForeignKey("expense_request.id"), index=True)
    uploaded_by_id: Mapped[int] = mapped_column(ForeignKey("person.id"))
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(255))
    size: Mapped[int] = mapped_column(BigInteger)
    storage_key: Mapped[str] = mapped_column(String(512), unique=True)
    created_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    request: Mapped[ExpenseRequest] = relationship(back_populates="attachments")
