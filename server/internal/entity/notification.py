import datetime

from approck_sqlalchemy_utils.model import Base
from sqlalchemy import TIMESTAMP, BigInteger, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from internal.entity.expense_request import ExpenseRequest, JournalEntry, Payment
from internal.entity.person import Person


class TelegramLink(Base):
    """The Telegram chat a person gets messages in.

    Made and removed by the person. Kept apart from the person, whose row is rewritten
    from the identity provider at a sign-in.
    """

    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"), unique=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


class TelegramLinkCode(Base):
    """A code a person starts the bot with to link their chat. Works once, for a short time."""

    code: Mapped[str] = mapped_column(String(64), unique=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"))
    expires_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP(timezone=True))
    used_at: Mapped[datetime.datetime | None] = mapped_column(TIMESTAMP(timezone=True))


class TelegramCursor(Base):
    """Where the service stopped reading what the bot was told. One row."""

    next_update_id: Mapped[int] = mapped_column(BigInteger)


class TelegramIntent(Base):
    """A decision offered to a person as a button under a message of the bot.

    The button carries the token alone, so pressing it can do nothing the person was not
    offered. An intent is carried out once; one that waits for a reason is carried out by
    the next message the person writes.
    """

    #: What the button sends back.
    token: Mapped[str] = mapped_column(String(32), unique=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"), index=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("expense_request.id"))
    #: The action of the transitions table the button stands for.
    action: Mapped[str] = mapped_column(String(16))
    #: ``offered``, ``awaiting_reason`` or ``done``.
    state: Mapped[str] = mapped_column(String(16))
    #: The message the button stands under.
    chat_id: Mapped[int] = mapped_column(BigInteger)
    message_id: Mapped[int | None] = mapped_column(BigInteger)
    #: The message that asks for the reason, while the intent waits for one: its buttons go with the answer.
    question_message_id: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    person: Mapped[Person] = relationship(lazy="joined")


class Notification(Base):
    """A message to a person about a request, written in the transaction of what it tells about.

    A row waits until it is sent or dropped: a message that no longer holds, or whose
    recipient has no chat any more, is dropped without being sent.
    """

    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"))
    request_id: Mapped[int] = mapped_column(ForeignKey("expense_request.id"))
    #: The name of the notice in the registry of notices.
    kind: Mapped[str] = mapped_column(String(32))
    #: The decision or the comment the message tells about.
    journal_entry_id: Mapped[int | None] = mapped_column(ForeignKey("journal_entry.id"))
    #: The payment the message tells about.
    payment_id: Mapped[int | None] = mapped_column(ForeignKey("payment.id"))
    #: Set for a message nobody's action stands behind, so that it is written once.
    once_key: Mapped[str | None] = mapped_column(String(128), unique=True)
    created_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    sent_at: Mapped[datetime.datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    dropped_at: Mapped[datetime.datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    person: Mapped[Person] = relationship(lazy="joined")
    request: Mapped[ExpenseRequest] = relationship(lazy="joined")
    journal_entry: Mapped[JournalEntry | None] = relationship(lazy="joined")
    payment: Mapped[Payment | None] = relationship(lazy="joined")
