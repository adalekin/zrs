"""The kinds of messages people are sent about requests.

A kind is a class: it says who a message of this kind is for when something happens
to a request, whether a message written earlier still holds, and what it reads. The
sender finds the class by the name a waiting message carries and knows no kind itself.
"""

import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import ClassVar, Literal

from internal.entity.enums import Party, Status
from internal.entity.expense_request import ExpenseRequest, JournalEntry, Payment

Locale = Literal["ru", "en"]


@dataclass(frozen=True)
class Occasion:
    """What has just happened to a request, as the notices see it."""

    request: ExpenseRequest
    #: Who did it. Nobody is told about what they did themselves.
    actor_id: int
    #: The people the request waited for before, and the ones it waits for now.
    awaited_before: frozenset[int]
    awaited_now: frozenset[int]
    #: The status the request has just come to, when it changed.
    became: Status | None = None
    #: The journal entry of the decision or of the comment.
    journal_entry: JournalEntry | None = None
    payment: Payment | None = None
    #: A comment that changed nothing else.
    commented: bool = False


@dataclass(frozen=True)
class Letter:
    """What a message is written from."""

    request: ExpenseRequest
    journal_entry: JournalEntry | None
    payment: Payment | None
    #: The address of the page of the request.
    url: str


class Words:
    """The wording of the messages in one language of the interface."""

    _PHRASES: ClassVar[dict[Locale, dict[str, str]]] = {
        "ru": {
            "awaits": "Запрос № {id} ждёт вашего действия",
            "approved": "Ваш запрос № {id} одобрен",
            "rejected_by_moderator": "Ваш запрос № {id} отклонил модератор {name}",
            "rejected_by_finance_director": "Ваш запрос № {id} отклонил финансовый директор",
            "paid": "По вашему запросу № {id} отмечена оплата",
            "commented": "{name} пишет о запросе № {id}",
            "priority": "приоритет: {name}",
            "deadline": "дедлайн {day}",
            "comment": "Комментарий: {text}",
        },
        "en": {
            "awaits": "Request No. {id} waits for your action",
            "approved": "Your request No. {id} is approved",
            "rejected_by_moderator": "Your request No. {id} was rejected by the moderator {name}",
            "rejected_by_finance_director": "Your request No. {id} was rejected by the finance director",
            "paid": "A payment is marked for your request No. {id}",
            "commented": "{name} writes about request No. {id}",
            "priority": "priority: {name}",
            "deadline": "deadline {day}",
            "comment": "Comment: {text}",
        },
    }

    def __init__(self, locale: Locale) -> None:
        self._locale = locale
        self._phrases = self._PHRASES[locale]

    def say(self, phrase: str, **values: object) -> str:
        return self._phrases[phrase].format(**values)

    def day(self, value: datetime.date) -> str:
        return value.strftime("%d.%m.%Y") if self._locale == "ru" else value.isoformat()

    def amount(self, value: Decimal, currency: str) -> str:
        grouped = f"{value:,.2f}"
        if self._locale == "ru":
            grouped = grouped.replace(",", " ").replace(".", ",")
        return f"{grouped} {currency}"


class Notice(ABC):
    kind: ClassVar[str]

    @abstractmethod
    def recipients(self, occasion: Occasion) -> frozenset[int]:
        """The people to tell about the occasion, before the one who caused it is left out."""

    def still_holds(self, request: ExpenseRequest, person_id: int, awaited_now: frozenset[int]) -> bool:
        """Whether a message written earlier is still worth sending. News of what happened always is."""
        return True

    @abstractmethod
    def text(self, letter: Letter, words: Words) -> str: ...

    @staticmethod
    def _gist(request: ExpenseRequest) -> str:
        return request.situation.split("\n", 1)[0]


class AwaitsAction(Notice):
    """The request has come into the queue of a person."""

    kind = "awaits_action"

    def recipients(self, occasion: Occasion) -> frozenset[int]:
        return occasion.awaited_now - occasion.awaited_before

    def still_holds(self, request: ExpenseRequest, person_id: int, awaited_now: frozenset[int]) -> bool:
        return person_id in awaited_now

    def text(self, letter: Letter, words: Words) -> str:
        request = letter.request
        facts = [
            words.amount(request.amount, request.currency),
            words.say("priority", name=request.priority.name),
        ]
        if request.deadline is not None:
            facts.append(words.say("deadline", day=words.day(request.deadline)))
        return "\n".join([words.say("awaits", id=request.id), self._gist(request), " · ".join(facts), letter.url])


class Approved(Notice):
    kind = "approved"

    def recipients(self, occasion: Occasion) -> frozenset[int]:
        return frozenset({occasion.request.author_id}) if occasion.became is Status.APPROVED else frozenset()

    def text(self, letter: Letter, words: Words) -> str:
        request = letter.request
        return "\n".join(
            [
                words.say("approved", id=request.id),
                self._gist(request),
                words.amount(request.amount, request.currency),
                letter.url,
            ]
        )


class Rejected(Notice):
    kind = "rejected"

    def recipients(self, occasion: Occasion) -> frozenset[int]:
        return frozenset({occasion.request.author_id}) if occasion.became is Status.REJECTED else frozenset()

    def text(self, letter: Letter, words: Words) -> str:
        request = letter.request
        if request.rejected_as == Party.MODERATOR.value and request.rejected_by is not None:
            headline = words.say("rejected_by_moderator", id=request.id, name=request.rejected_by.name)
        else:
            headline = words.say("rejected_by_finance_director", id=request.id)
        lines = [headline, self._gist(request)]
        if letter.journal_entry is not None and letter.journal_entry.comment:
            lines.append(words.say("comment", text=letter.journal_entry.comment))
        return "\n".join([*lines, letter.url])


class Paid(Notice):
    """A payment of the request is marked: every one of them, for a request paid every period."""

    kind = "paid"

    def recipients(self, occasion: Occasion) -> frozenset[int]:
        return frozenset({occasion.request.author_id}) if occasion.payment is not None else frozenset()

    def text(self, letter: Letter, words: Words) -> str:
        request, payment = letter.request, letter.payment
        if payment is None:
            raise ValueError("A message about a payment needs the payment")
        paid = f"{words.amount(payment.amount, request.currency)} · {words.day(payment.paid_on)}"
        return "\n".join([words.say("paid", id=request.id), self._gist(request), paid, letter.url])


class Commented(Notice):
    kind = "commented"

    def recipients(self, occasion: Occasion) -> frozenset[int]:
        if not occasion.commented:
            return frozenset()
        return frozenset({occasion.request.author_id, occasion.request.moderator_id})

    def text(self, letter: Letter, words: Words) -> str:
        entry = letter.journal_entry
        if entry is None or entry.comment is None:
            raise ValueError("A message about a comment needs the comment")
        return "\n".join(
            [
                words.say("commented", name=entry.person.name, id=letter.request.id),
                self._gist(letter.request),
                entry.comment,
                letter.url,
            ]
        )


#: Every kind of message by its name.
NOTICES: dict[str, Notice] = {
    notice.kind: notice for notice in (AwaitsAction(), Approved(), Rejected(), Paid(), Commented())
}
