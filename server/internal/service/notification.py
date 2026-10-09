import datetime

from approck_services.base import BaseService
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from internal.config import settings
from internal.entity.enums import Status
from internal.entity.expense_request import ExpenseRequest
from internal.entity.notification import Notification, TelegramLink
from internal.entity.person import Person
from internal.entity.recurrence import Recurrence
from internal.service.notices import NOTICES, AwaitsAction, Letter, Occasion, Words
from internal.service.queue import Queue
from internal.service.telegram import ChatClosed, TelegramGateway, TelegramUnavailable
from internal.service.telegram_decisions import DecisionOffer


class NotificationService(BaseService):
    """Writes messages about requests next to what they tell about, and sends the ones that wait.

    A message is a row written in the transaction of the action (a transactional outbox),
    so an action never waits for Telegram and a message is never lost with a stopped server.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__()
        self.session = session

    @property
    def enabled(self) -> bool:
        return settings.NOTIFICATIONS == "telegram"

    # --- writing, in the transaction of an action ---

    async def awaited(self, request: ExpenseRequest, today: datetime.date) -> frozenset[int]:
        """The people the request waits for now."""
        if not self.enabled:
            return frozenset()
        ids = await self.session.scalars(select(Person.id).where(Queue(today).people_awaited_by(request)))
        return frozenset(ids)

    async def announce(self, occasion: Occasion) -> None:
        """Write a message to everyone a notice names, the linked ones among them."""
        if not self.enabled:
            return
        for notice in NOTICES.values():
            people = notice.recipients(occasion) - {occasion.actor_id}
            for person_id in await self._linked(people):
                self.session.add(
                    Notification(
                        person_id=person_id,
                        request_id=occasion.request.id,
                        kind=notice.kind,
                        journal_entry_id=occasion.journal_entry.id if occasion.journal_entry else None,
                        payment_id=occasion.payment.id if occasion.payment else None,
                    )
                )

    async def _linked(self, people: frozenset[int]) -> list[int]:
        if not people:
            return []
        linked = await self.session.scalars(
            select(TelegramLink.person_id).where(TelegramLink.person_id.in_(people)).order_by(TelegramLink.person_id)
        )
        return list(linked)

    # --- sending, by the background task ---

    async def announce_new_periods(self, today: datetime.date) -> None:
        """Tell the payers about the recurring requests a new period has brought back.

        Nobody's action stands behind such a message, so it carries a key of the request,
        the person and the first day of the period, and the database keeps it single.
        """
        queue = Queue(today)
        back = await self.session.scalars(
            select(ExpenseRequest).where(
                ExpenseRequest.status == Status.APPROVED.value,
                ExpenseRequest.recurrence.is_not(None),
                ExpenseRequest.paid_on.is_not(None),
                ExpenseRequest.paid_on < queue.period_start(),
            )
        )
        for request in back:
            period = Recurrence(request.recurrence).period_start(today)
            for person_id in await self._linked(await self.awaited(request, today)):
                await self.session.execute(
                    insert(Notification)
                    .values(
                        person_id=person_id,
                        request_id=request.id,
                        kind=AwaitsAction.kind,
                        once_key=f"period:{request.id}:{person_id}:{period.isoformat()}",
                    )
                    .on_conflict_do_nothing(index_elements=[Notification.once_key])
                )
        await self.session.commit()

    async def send_next(self, gateway: TelegramGateway, today: datetime.date) -> bool:
        """Send the oldest waiting message, in a transaction of its own. False when none waits.

        The row is locked so that another replica takes another message. It is marked right
        after Telegram answers: a server stopped in between sends the message again, and
        nothing shorter than that can be promised to a person.
        """
        message = await self.session.scalar(
            select(Notification)
            .where(Notification.sent_at.is_(None), Notification.dropped_at.is_(None))
            .order_by(Notification.id)
            .limit(1)
            .with_for_update(skip_locked=True, of=Notification)
            # One session sends many messages, and each must see the request as it is now. A locking read
            # refreshes what it loads already; it is said outright because the sender relies on it.
            .execution_options(populate_existing=True)
        )
        if message is None:
            await self.session.rollback()
            return False

        link = await self.session.scalar(select(TelegramLink).where(TelegramLink.person_id == message.person_id))
        notice = NOTICES[message.kind]
        awaited = await self.awaited(message.request, today)
        if link is None or not notice.still_holds(message.request, message.person_id, awaited):
            message.dropped_at = func.now()
            await self.session.commit()
            return True

        letter = Letter(
            request=message.request,
            journal_entry=message.journal_entry,
            payment=message.payment,
            url=f"{settings.AUTH_ORIGIN}/requests/{message.request_id}",
            new_period=message.once_key is not None,
        )
        words = Words(settings.UI_LOCALE)
        # The decisions open to the reader go under the message as buttons, when the installation allows it.
        intents = []
        if notice.offers_decisions and settings.TELEGRAM_DECISIONS == "on":
            intents = await DecisionOffer(self.session).offer(message.person, message.request, link.chat_id)
        keyboard = DecisionOffer.keyboard(intents, message.request, words)
        try:
            sent = await gateway.send_message(link.chat_id, notice.text(letter, words), keyboard)
        except ChatClosed:
            # The person blocked the bot: there is no chat to write to any more.
            logger.info("Telegram chat of person {} is closed, the link is removed", message.person_id)
            for intent in intents:
                await self.session.delete(intent)
            await self.session.delete(link)
            message.dropped_at = func.now()
            await self.session.commit()
            return True
        except TelegramUnavailable:
            await self.session.rollback()
            raise

        for intent in intents:
            intent.message_id = sent
        message.sent_at = func.now()
        await self.session.commit()
        return True
