"""Decisions on requests offered as buttons under the messages of the bot.

A button carries a token of an intent stored in the database: the person, the request and
the action. Pressing it can therefore do nothing the person was not offered, and what is
offered comes from the transitions table, as the actions of the service do.
"""

import secrets

from approck_services.base import BaseService
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from internal.entity.enums import Action, Status
from internal.entity.expense_request import ExpenseRequest
from internal.entity.notification import TelegramIntent
from internal.entity.person import Person
from internal.service import transitions
from internal.service.actor import Actor
from internal.service.notices import Words
from internal.service.telegram import Button, Keyboard

#: The decisions of an approver, in the order of their buttons. Paying, resubmitting, cancelling
#: and editing stay in the service.
DECISIONS: tuple[Action, ...] = (Action.APPROVE, Action.ESCALATE, Action.RETURN, Action.REJECT)
#: The decisions whose reason the author needs: the bot asks for it before it acts.
ASK_REASON: frozenset[Action] = frozenset({Action.RETURN, Action.REJECT})

OFFERED = "offered"
AWAITING_REASON = "awaiting_reason"
DONE = "done"

#: What the two buttons under the question about the reason add to the token.
WITHOUT_COMMENT = "skip"
CANCEL = "cancel"


class DecisionOffer(BaseService):
    """Offers a person the decisions open to them on a request, and keeps what was offered."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__()
        self.session = session

    async def offer(self, person: Person, request: ExpenseRequest, chat_id: int) -> list[TelegramIntent]:
        """An intent for every decision the person may take on the request now."""
        available = transitions.available_actions(Actor.as_last_signed_in(person), request)
        intents = [
            TelegramIntent(
                token=secrets.token_urlsafe(16),
                person_id=person.id,
                request_id=request.id,
                action=action.value,
                state=OFFERED,
                chat_id=chat_id,
            )
            for action in DECISIONS
            if action in available
        ]
        self.session.add_all(intents)
        await self.session.flush()
        return intents

    @staticmethod
    def keyboard(intents: list[TelegramIntent], request: ExpenseRequest, words: Words) -> Keyboard | None:
        """The buttons of the offered decisions, two in a row."""
        if not intents:
            return None
        buttons = [Button(words.say(DecisionOffer._label(intent, request)), intent.token) for intent in intents]
        return [buttons[index : index + 2] for index in range(0, len(buttons), 2)]

    @staticmethod
    def reason_keyboard(intent: TelegramIntent, words: Words) -> Keyboard:
        return [
            [
                Button(words.say("without_comment"), f"{intent.token}:{WITHOUT_COMMENT}"),
                Button(words.say("cancel"), f"{intent.token}:{CANCEL}"),
            ]
        ]

    @staticmethod
    def _label(intent: TelegramIntent, request: ExpenseRequest) -> str:
        if intent.action == Action.APPROVE.value:
            # The moderator approves a new request, the finance director one passed on to them.
            return "do_approve_new" if request.status == Status.NEW.value else "do_approve_escalated"
        return f"do_{intent.action}"

    async def find(self, token: str) -> TelegramIntent | None:
        """The intent of a button, locked: two presses of one button are carried out one after the other."""
        return await self.session.scalar(
            select(TelegramIntent).where(TelegramIntent.token == token).with_for_update(of=TelegramIntent)
        )

    async def awaiting_reason(self, person_id: int, chat_id: int) -> TelegramIntent | None:
        return await self.session.scalar(
            select(TelegramIntent)
            .where(
                TelegramIntent.person_id == person_id,
                TelegramIntent.chat_id == chat_id,
                TelegramIntent.state == AWAITING_REASON,
            )
            .with_for_update(of=TelegramIntent)
        )

    async def stop_awaiting_reason(self, person_id: int, *, but: int) -> None:
        """A person waits to be asked for one reason at a time: another button takes the question back."""
        await self.session.execute(
            update(TelegramIntent)
            .where(
                TelegramIntent.person_id == person_id,
                TelegramIntent.state == AWAITING_REASON,
                TelegramIntent.id != but,
            )
            .values(state=OFFERED, question_message_id=None)
        )

    async def remember_question(self, intent_id: int, message_id: int) -> None:
        """Keep the number of the message that asks for the reason. A transaction of its own, after the sending."""
        await self.session.execute(
            update(TelegramIntent)
            .where(TelegramIntent.id == intent_id, TelegramIntent.state == AWAITING_REASON)
            .values(question_message_id=message_id)
        )
        await self.session.commit()

    async def close(self, intent: TelegramIntent) -> None:
        """The request is decided: none of the buttons of this message stands any more."""
        await self.session.execute(
            update(TelegramIntent)
            .where(
                TelegramIntent.person_id == intent.person_id,
                TelegramIntent.request_id == intent.request_id,
                TelegramIntent.state != DONE,
            )
            .values(state=DONE)
        )
