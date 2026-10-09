"""What the service does with what its bot is told: one handler for each kind of update.

The listener reads the updates and finds a handler by the kind of the event; it knows no
kind itself. A handler changes the database inside the transaction of the reading and
leaves the answers to the person on the desk: they are sent after the transaction is
committed, so a person is never told of something that did not happen.
"""

import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from approck_fastapi_utils.exceptions import Forbidden, NotFound
from approck_services.base import BaseService
from approck_sqlalchemy_utils.transaction import atomic
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from internal.config import settings
from internal.entity.enums import Action
from internal.entity.expense_request import ExpenseRequest
from internal.entity.notification import TelegramCursor, TelegramIntent
from internal.exceptions import StatusConflict
from internal.service.actor import Actor
from internal.service.expense_request import ExpenseRequestService
from internal.service.notices import Words
from internal.service.telegram import (
    Blocked,
    ChatClosed,
    Event,
    Keyboard,
    Pressed,
    Said,
    Started,
    TelegramGateway,
    TelegramUnavailable,
)
from internal.service.telegram_decisions import (
    ASK_REASON,
    AWAITING_REASON,
    CANCEL,
    DONE,
    OFFERED,
    WITHOUT_COMMENT,
    DecisionOffer,
)
from internal.service.telegram_link import TelegramLinkService

#: How long one call waits for the bot to be told something.
POLL_SECONDS = 25


@dataclass(frozen=True)
class Message:
    chat_id: int
    #: Telegram HTML.
    text: str
    keyboard: Keyboard | None = None
    #: The earlier message of the chat this one answers.
    reply_to: int | None = None
    #: The intent this message asks the reason of: it remembers the number the message gets.
    asks_reason_of: int | None = None


@dataclass(frozen=True)
class PressAnswer:
    press_id: str
    text: str


@dataclass(frozen=True)
class KeyboardChange:
    chat_id: int
    message_id: int
    keyboard: Keyboard | None


Reply = Message | PressAnswer | KeyboardChange


@dataclass
class Desk:
    """What a handler works with: the transaction of the reading, the day, and the answers to send after it."""

    session: AsyncSession
    today: datetime.date
    words: Words
    replies: list[Reply] = field(default_factory=list)


class Handler[E: Event](ABC):
    @abstractmethod
    async def handle(self, event: E, desk: Desk) -> None: ...


class LinkChat(Handler[Started]):
    """A person started the bot: with a link of the service their chat is linked to them."""

    async def handle(self, event: Started, desk: Desk) -> None:
        if event.parameter is not None and await TelegramLinkService(desk.session).redeem(
            event.parameter, event.chat_id
        ):
            desk.replies.append(Message(event.chat_id, desk.words.html("linked")))
            return
        # Without a link of the service the bot says where to get one; with a dead one, that it is dead.
        said = desk.words.html("how_to_link" if event.parameter is None else "invalid_link")
        page = f'<a href="{settings.AUTH_ORIGIN}/notifications">{desk.words.html("notifications_page")}</a>'
        desk.replies.append(Message(event.chat_id, f"{said}\n{page}"))


class UnlinkChat(Handler[Blocked]):
    """A person blocked the bot: there is no chat to write to any more."""

    async def handle(self, event: Blocked, desk: Desk) -> None:
        await TelegramLinkService(desk.session).unlink_chat(event.chat_id)


class Decide:
    """Carries out an intent on behalf of the person it was offered to, the way the service does."""

    @staticmethod
    async def carry_out(intent: TelegramIntent, comment: str | None, desk: Desk) -> str:
        """Apply the action and close the buttons. Returns what to tell the person."""
        actor = Actor.as_last_signed_in(intent.person)
        requests = ExpenseRequestService(session=desk.session)
        try:
            await requests.act(
                actor, intent.request_id, Action(intent.action), comment=comment, parameters={}, today=desk.today
            )
        except StatusConflict as conflict:
            outcome = desk.words.say(
                "already", id=intent.request_id, status=desk.words.say(f"status_{conflict.status.value}")
            )
        except (Forbidden, NotFound):
            outcome = desk.words.say("not_available")
        else:
            outcome = (
                f"{desk.words.say(f'done_{intent.action}', id=intent.request_id)}. {desk.words.say('author_is_told')}"
            )

        await DecisionOffer(desk.session).close(intent)
        # The buttons go from under the message about the request and from under the question about the reason.
        for message_id in (intent.message_id, intent.question_message_id):
            if message_id is not None:
                desk.replies.append(KeyboardChange(intent.chat_id, message_id, None))
        return outcome


class PressButton(Handler[Pressed], Decide):
    """A person pressed a button under a message: a decision, or an answer to the question about its reason."""

    async def handle(self, event: Pressed, desk: Desk) -> None:
        if settings.TELEGRAM_DECISIONS != "on":
            desk.replies.append(PressAnswer(event.press_id, desk.words.say("button_gone")))
            return

        token, _, choice = event.data.partition(":")
        offers = DecisionOffer(desk.session)
        intent = await offers.find(token)
        if intent is None or intent.chat_id != event.chat_id:
            desk.replies.append(PressAnswer(event.press_id, desk.words.say("button_gone")))
            return
        if not await TelegramLinkService(desk.session).links(intent.person_id, event.chat_id):
            desk.replies.append(PressAnswer(event.press_id, desk.words.say("chat_not_linked")))
            desk.replies.append(KeyboardChange(event.chat_id, event.message_id, None))
            return

        await offers.stop_awaiting_reason(intent.person_id, but=intent.id)
        if intent.state == DONE:
            status = await desk.session.scalar(
                select(ExpenseRequest.status).where(ExpenseRequest.id == intent.request_id)
            )
            told = desk.words.say("already", id=intent.request_id, status=desk.words.say(f"status_{status}"))
            desk.replies += [PressAnswer(event.press_id, told), KeyboardChange(event.chat_id, event.message_id, None)]
            return

        if choice == CANCEL:
            intent.state = OFFERED
            intent.question_message_id = None
            desk.replies += [
                PressAnswer(event.press_id, desk.words.say("cancelled")),
                KeyboardChange(event.chat_id, event.message_id, None),
            ]
            return
        if choice == "" and Action(intent.action) in ASK_REASON:
            intent.state = AWAITING_REASON
            question = desk.words.html(f"ask_reason_{intent.action}", id=intent.request_id)
            desk.replies += [
                PressAnswer(event.press_id, desk.words.say("write_reason")),
                Message(
                    event.chat_id,
                    question,
                    DecisionOffer.reason_keyboard(intent, desk.words),
                    reply_to=intent.message_id,
                    asks_reason_of=intent.id,
                ),
            ]
            return
        if choice not in ("", WITHOUT_COMMENT) or (choice == WITHOUT_COMMENT and intent.state != AWAITING_REASON):
            desk.replies.append(PressAnswer(event.press_id, desk.words.say("button_gone")))
            return

        outcome = await self.carry_out(intent, None, desk)
        desk.replies += [
            PressAnswer(event.press_id, outcome),
            Message(event.chat_id, outcome, reply_to=intent.message_id),
        ]


class SayReason(Handler[Said], Decide):
    """A person wrote to the bot: the reason it asked for, or something nobody asked."""

    async def handle(self, event: Said, desk: Desk) -> None:
        if settings.TELEGRAM_DECISIONS != "on":
            return
        person_id = await TelegramLinkService(desk.session).person_of(event.chat_id)
        intent = person_id and await DecisionOffer(desk.session).awaiting_reason(person_id, event.chat_id)
        if not intent:
            desk.replies.append(Message(event.chat_id, desk.words.html("idle")))
            return
        outcome = await self.carry_out(intent, event.text.strip(), desk)
        desk.replies.append(Message(event.chat_id, outcome, reply_to=intent.message_id))


#: The handler of every kind of update the service has a use for.
HANDLERS: dict[type, Handler] = {
    Started: LinkChat(),
    Blocked: UnlinkChat(),
    Pressed: PressButton(),
    Said: SayReason(),
}


class BotListener(BaseService):
    """Reads what the bot was told since the last time and hands every update to its handler."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__()
        self.session = session

    async def read_updates(
        self, gateway: TelegramGateway, today: datetime.date, *, wait_seconds: int = POLL_SECONDS
    ) -> bool:
        """One reading. False when another reader is at it.

        Telegram gives the updates of a bot to one reader, so the reading holds a lock for
        its transaction. The position moves in the same transaction as what the updates
        did: an update is not acted on twice, whatever stops the server.
        """
        desk = Desk(session=self.session, today=today, words=Words(settings.UI_LOCALE))
        async with atomic(self.session):
            got = await self.session.scalar(select(func.pg_try_advisory_xact_lock(func.hashtext("telegram.updates"))))
            if not got:
                return False

            cursor = await self.session.scalar(select(TelegramCursor))
            updates = await gateway.get_updates(cursor.next_update_id if cursor else None, wait_seconds)
            for update in updates:
                handler = HANDLERS.get(type(update.event))
                if handler is not None:
                    await handler.handle(update.event, desk)
            if updates:
                position = updates[-1].id + 1
                if cursor is None:
                    self.session.add(TelegramCursor(next_update_id=position))
                else:
                    cursor.next_update_id = position

        for reply in desk.replies:
            try:
                match reply:
                    case Message(chat_id=chat_id, text=text, keyboard=keyboard, reply_to=reply_to):
                        number = await gateway.send_message(chat_id, text, keyboard, reply_to=reply_to)
                        if reply.asks_reason_of is not None:
                            await DecisionOffer(self.session).remember_question(reply.asks_reason_of, number)
                    case PressAnswer(press_id=press_id, text=text):
                        await gateway.answer_press(press_id, text)
                    case KeyboardChange(chat_id=chat_id, message_id=message_id, keyboard=keyboard):
                        await gateway.set_keyboard(chat_id, message_id, keyboard)
            except (TelegramUnavailable, ChatClosed):
                # What the update did is committed; the person sees it in the service.
                continue
        return True
