"""The kinds of messages people are sent about requests.

A message is written for a phone: the first line says what happened and what is wanted of the
reader, the number of the request in it opens the request, the amount stands out, and the words
of another person (a reason, a comment) are set apart as a quotation. The texts are Telegram HTML.

A kind is a class: it says who a message of this kind is for when something happens
to a request, whether a message written earlier still holds, and what it reads. The
sender finds the class by the name a waiting message carries and knows no kind itself.
"""

import datetime
import html
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
    #: The request came back to its payer with a new period, by nobody's action.
    new_period: bool = False


#: The longest first line of a situation and the longest quotation a message carries.
GIST_LIMIT = 200
QUOTE_LIMIT = 700


class Words:
    """The wording of the messages in one language of the interface."""

    _PHRASES: ClassVar[dict[Locale, dict[str, str]]] = {
        "ru": {
            "request": "запрос № {id}",
            "awaits_new": "{Request} ждёт вашего решения",
            "awaits_escalated": "{Request} передан вам на одобрение",
            "awaits_approved": "{Request} одобрен и ждёт оплаты",
            "awaits_returned": "{Request} вернули вам на исправление",
            "awaits_period": "{Request}: пора платить за новый период",
            "approved": "Ваш {request} одобрен",
            "rejected": "Ваш {request} отклонён",
            "request_about": "запросе № {id}",
            "paid": "{Request}: отмечена оплата",
            "commented": "{name} о {about_request}",
            "until": "до {day}",
            "author": "Автор: {name}",
            "moderator": "Модератор: {name}",
            "approved_by": "Одобрено: {name}",
            "returned_by": "Возврат: {name}",
            "rejected_by_moderator": "Отказ: модератор {name}",
            "rejected_by_finance_director": "Отказ: финансовый директор",
            "recurrence_week": "еженедельно",
            "recurrence_month": "ежемесячно",
            "recurrence_quarter": "ежеквартально",
            "recurrence_year": "ежегодно",
            "linked": "Telegram привязан. Сюда будут приходить сообщения о запросах: когда запрос ждёт вашего действия, "
            "когда по вашему запросу принято решение и когда к нему оставили комментарий.",
            "how_to_link": "Чтобы получать сообщения о запросах, откройте в сервисе страницу «Уведомления» "
            "и нажмите «Привязать Telegram».",
            "invalid_link": "Эта ссылка уже не действует. Получите новую на странице «Уведомления» в сервисе.",
            "notifications_page": "Открыть страницу «Уведомления»",
            "do_approve_new": "Утвердить",
            "do_approve_escalated": "Одобрить",
            "do_escalate": "Финдиректору",
            "do_return": "Вернуть",
            "do_reject": "Отклонить",
            "without_comment": "Без комментария",
            "cancel": "Отмена",
            "ask_reason_return": "Что автору исправить в запросе № {id}? Напишите ответным сообщением.",
            "ask_reason_reject": "Почему запрос № {id} отклонён? Напишите ответным сообщением.",
            "write_reason": "Напишите причину сообщением",
            "done_approve": "Запрос № {id} одобрен",
            "done_escalate": "Запрос № {id} передан финансовому директору",
            "done_return": "Запрос № {id} возвращён автору",
            "done_reject": "Запрос № {id} отклонён",
            "author_is_told": "Автор получит сообщение.",
            "already": "Запрос № {id} уже в статусе «{status}»",
            "not_available": "Это действие вам недоступно",
            "button_gone": "Кнопка больше не действует",
            "chat_not_linked": "Этот чат не привязан к сервису",
            "cancelled": "Действие отменено",
            "idle": "Я пишу о запросах и принимаю решения по кнопкам под сообщениями. Остальное делается в сервисе.",
            "status_new": "Новая",
            "status_returned": "Ошибка",
            "status_escalated": "Отмодерировано",
            "status_approved": "Одобрено",
            "status_paid": "Оплачено",
            "status_rejected": "Отказ",
        },
        "en": {
            "request": "request No. {id}",
            "awaits_new": "{Request} waits for your decision",
            "awaits_escalated": "{Request} is passed to you for approval",
            "awaits_approved": "{Request} is approved and waits for payment",
            "awaits_returned": "{Request} is returned to you for correction",
            "awaits_period": "{Request}: a payment for the new period is due",
            "approved": "Your {request} is approved",
            "rejected": "Your {request} is rejected",
            "request_about": "request No. {id}",
            "paid": "{Request}: a payment is marked",
            "commented": "{name} about {about_request}",
            "until": "by {day}",
            "author": "Author: {name}",
            "moderator": "Moderator: {name}",
            "approved_by": "Approved by {name}",
            "returned_by": "Returned by {name}",
            "rejected_by_moderator": "Rejected by the moderator {name}",
            "rejected_by_finance_director": "Rejected by the finance director",
            "recurrence_week": "weekly",
            "recurrence_month": "monthly",
            "recurrence_quarter": "quarterly",
            "recurrence_year": "yearly",
            "linked": "Telegram is linked. Messages about requests will come here: when a request waits for your "
            "action, when your request is decided on and when somebody comments on it.",
            "how_to_link": "To get messages about requests, open the Notifications page of the service "
            "and press Link Telegram.",
            "invalid_link": "This link does not work any more. Get a new one on the Notifications page of the service.",
            "notifications_page": "Open the Notifications page",
            "do_approve_new": "Approve",
            "do_approve_escalated": "Approve",
            "do_escalate": "To the director",
            "do_return": "Return",
            "do_reject": "Reject",
            "without_comment": "Without a comment",
            "cancel": "Cancel",
            "ask_reason_return": "What should the author correct in request No. {id}? Write it in a reply.",
            "ask_reason_reject": "Why is request No. {id} rejected? Write it in a reply.",
            "write_reason": "Write the reason in a message",
            "done_approve": "Request No. {id} is approved",
            "done_escalate": "Request No. {id} is passed to the finance director",
            "done_return": "Request No. {id} is returned to the author",
            "done_reject": "Request No. {id} is rejected",
            "author_is_told": "The author will get a message.",
            "already": "Request No. {id} is already in the status '{status}'",
            "not_available": "This action is not available to you",
            "button_gone": "The button does not work any more",
            "chat_not_linked": "This chat is not linked to the service",
            "cancelled": "The action is cancelled",
            "idle": "I write about requests and take decisions by the buttons under my messages. "
            "The rest is done in the service.",
            "status_new": "New",
            "status_returned": "Returned",
            "status_escalated": "Moderated",
            "status_approved": "Approved",
            "status_paid": "Paid",
            "status_rejected": "Rejected",
        },
    }
    #: The signs of the currencies people know by sight; the rest go by their code.
    _SIGNS: ClassVar[dict[str, str]] = {"RUB": "₽", "USD": "$", "EUR": "€"}

    def __init__(self, locale: Locale) -> None:
        self._locale = locale
        self._phrases = self._PHRASES[locale]

    def say(self, phrase: str, **values: object) -> str:
        """A phrase as plain text: for a button and for the notice over the chat."""
        return self._phrases[phrase].format(**values)

    def html(self, phrase: str, **values: object) -> str:
        """A phrase for the text of a message: what is put into it is escaped."""
        return self._phrases[phrase].format(**{name: escape(str(value)) for name, value in values.items()})

    def headline(self, phrase: str, request_id: int, url: str, **values: object) -> str:
        """A phrase that names the request, with the name opening the page of the request."""

        def link(name: str) -> str:
            return f'<a href="{html.escape(url)}">{name}</a>'

        name = self.say("request", id=request_id)
        return self._phrases[phrase].format(
            request=link(name),
            Request=link(name[0].upper() + name[1:]),
            about_request=link(self.say("request_about", id=request_id)),
            **{key: escape(str(value)) for key, value in values.items()},
        )

    def day(self, value: datetime.date) -> str:
        return value.strftime("%d.%m.%Y") if self._locale == "ru" else value.isoformat()

    def amount(self, value: Decimal, currency: str) -> str:
        grouped = f"{value:,.2f}"
        if self._locale == "ru":
            grouped = grouped.replace(",", " ").replace(".", ",")
        return f"{grouped} {self._SIGNS.get(currency, currency)}"


def escape(text: str) -> str:
    return html.escape(text, quote=False)


def shorten(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def bold(text: str) -> str:
    return f"<b>{text}</b>"


def quote(text: str) -> str:
    """The words of another person, set apart."""
    return f"<blockquote>{escape(shorten(text.strip(), QUOTE_LIMIT))}</blockquote>"


class Notice(ABC):
    kind: ClassVar[str]
    #: Whether a message of this kind carries the buttons of the decisions open to its reader.
    offers_decisions: ClassVar[bool] = False

    @abstractmethod
    def recipients(self, occasion: Occasion) -> frozenset[int]:
        """The people to tell about the occasion, before the one who caused it is left out."""

    def still_holds(self, request: ExpenseRequest, person_id: int, awaited_now: frozenset[int]) -> bool:
        """Whether a message written earlier is still worth sending. News of what happened always is."""
        return True

    @abstractmethod
    def text(self, letter: Letter, words: Words) -> str: ...

    # --- the parts every message is put together from ---

    @staticmethod
    def _headline(mark: str, phrase: str, letter: Letter, words: Words, **values: object) -> str:
        """What happened, in bold, with the number of the request opening the request."""
        return f"{mark} " + bold(words.headline(phrase, letter.request.id, letter.url, **values))

    @staticmethod
    def _gist(request: ExpenseRequest) -> str:
        return escape(shorten(request.situation.split("\n", 1)[0], GIST_LIMIT))

    @staticmethod
    def _facts(request: ExpenseRequest, words: Words, *, payment_form: bool = False) -> str:
        """The amount and what an approver or a payer weighs it against, in one line."""
        facts = [bold(words.amount(request.amount, request.currency)), escape(request.priority.name)]
        if payment_form and request.payment_form is not None:
            facts.append(escape(request.payment_form.name))
        if request.deadline is not None:
            facts.append(words.say("until", day=words.day(request.deadline)))
        if request.recurrence is not None:
            facts.append(words.say(f"recurrence_{request.recurrence}"))
        return " · ".join(facts)

    @staticmethod
    def _said(entry: JournalEntry | None) -> list[str]:
        """The comment of a decision, when it has one."""
        return [quote(entry.comment)] if entry is not None and entry.comment else []


class AwaitsAction(Notice):
    """The request has come into the queue of a person: the message says what is wanted of them."""

    kind = "awaits_action"
    offers_decisions = True

    #: The colours of the stages, as the list and the board paint them.
    _MARKS: ClassVar[dict[Status, str]] = {
        Status.NEW: "⚪",
        Status.RETURNED: "🟠",
        Status.ESCALATED: "🟡",
        Status.APPROVED: "🟢",
    }

    def recipients(self, occasion: Occasion) -> frozenset[int]:
        return occasion.awaited_now - occasion.awaited_before

    def still_holds(self, request: ExpenseRequest, person_id: int, awaited_now: frozenset[int]) -> bool:
        return person_id in awaited_now

    def text(self, letter: Letter, words: Words) -> str:
        request, entry = letter.request, letter.journal_entry
        status = Status(request.status)
        phrase = "awaits_period" if letter.new_period else f"awaits_{status.value}"
        lines = [self._headline(self._MARKS[status], phrase, letter, words), self._gist(request)]

        match status:
            case Status.RETURNED:
                # The author knows their own request: what they need is who sent it back and why.
                if entry is not None:
                    lines.append(words.html("returned_by", name=entry.person.name))
                lines += self._said(entry)
            case Status.APPROVED:
                lines.append(self._facts(request, words, payment_form=True))
                lines.append(words.html("author", name=request.author.name))
            case Status.ESCALATED:
                lines.append(self._facts(request, words))
                lines.append(
                    f"{words.html('author', name=request.author.name)} · "
                    f"{words.html('moderator', name=request.moderator.name)}"
                )
                lines += self._said(entry)
            case _:
                lines.append(self._facts(request, words))
                lines.append(words.html("author", name=request.author.name))
        return "\n".join(lines)


class Approved(Notice):
    kind = "approved"

    def recipients(self, occasion: Occasion) -> frozenset[int]:
        return frozenset({occasion.request.author_id}) if occasion.became is Status.APPROVED else frozenset()

    def text(self, letter: Letter, words: Words) -> str:
        request, entry = letter.request, letter.journal_entry
        lines = [self._headline("🟢", "approved", letter, words), self._gist(request)]
        lines.append(bold(words.amount(request.amount, request.currency)))
        if entry is not None:
            lines.append(words.html("approved_by", name=entry.person.name))
        return "\n".join(lines + self._said(entry))


class Rejected(Notice):
    kind = "rejected"

    def recipients(self, occasion: Occasion) -> frozenset[int]:
        return frozenset({occasion.request.author_id}) if occasion.became is Status.REJECTED else frozenset()

    def text(self, letter: Letter, words: Words) -> str:
        request = letter.request
        by_moderator = request.rejected_as == Party.MODERATOR.value and request.rejected_by is not None
        # Red for the finance director, as in the list: that rejection is about money and may be returned to.
        lines = [self._headline("⚫" if by_moderator else "🔴", "rejected", letter, words), self._gist(request)]
        if by_moderator:
            lines.append(words.html("rejected_by_moderator", name=request.rejected_by.name))
        else:
            lines.append(words.say("rejected_by_finance_director"))
        return "\n".join(lines + self._said(letter.journal_entry))


class Paid(Notice):
    """A payment of the request is marked: every one of them, for a request paid every period."""

    kind = "paid"

    def recipients(self, occasion: Occasion) -> frozenset[int]:
        return frozenset({occasion.request.author_id}) if occasion.payment is not None else frozenset()

    def text(self, letter: Letter, words: Words) -> str:
        request, payment = letter.request, letter.payment
        if payment is None:
            raise ValueError("A message about a payment needs the payment")
        paid = f"{bold(words.amount(payment.amount, request.currency))} · {words.day(payment.paid_on)}"
        return "\n".join([self._headline("✅", "paid", letter, words), self._gist(request), paid])


class Commented(Notice):
    kind = "commented"

    def recipients(self, occasion: Occasion) -> frozenset[int]:
        if not occasion.commented:
            return frozenset()
        return frozenset({occasion.request.author_id, occasion.request.moderator_id})

    def text(self, letter: Letter, words: Words) -> str:
        entry, request = letter.journal_entry, letter.request
        if entry is None or entry.comment is None:
            raise ValueError("A message about a comment needs the comment")
        headline = self._headline("💬", "commented", letter, words, name=entry.person.name)
        return "\n".join([headline, self._gist(request), quote(entry.comment)])


#: Every kind of message by its name.
NOTICES: dict[str, Notice] = {
    notice.kind: notice for notice in (AwaitsAction(), Approved(), Rejected(), Paid(), Commented())
}
