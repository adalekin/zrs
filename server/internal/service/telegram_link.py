import datetime
import secrets

from approck_services.base import BaseService
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from internal.config import settings
from internal.entity.notification import TelegramCursor, TelegramLink, TelegramLinkCode
from internal.service.notices import Locale
from internal.service.telegram import Blocked, ChatClosed, Started, TelegramGateway, TelegramUnavailable

#: How long a link that starts the bot works.
CODE_LIFETIME = datetime.timedelta(minutes=15)
#: How long one call waits for the bot to be told something.
POLL_SECONDS = 25

REPLIES: dict[Locale, dict[str, str]] = {
    "ru": {
        "linked": "Telegram привязан. Сюда будут приходить сообщения о запросах.",
        "invalid": "Ссылка недействительна. Получите новую на странице уведомлений в сервисе.",
    },
    "en": {
        "linked": "Telegram is linked. Messages about requests will come here.",
        "invalid": "The link is not valid. Get a new one on the notifications page of the service.",
    },
}


class TelegramLinkService(BaseService):
    """Links a person to their Telegram chat with a one-time code, and reads what the bot is told."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__()
        self.session = session

    async def is_linked(self, person_id: int) -> bool:
        return await self.session.scalar(select(TelegramLink.id).where(TelegramLink.person_id == person_id)) is not None

    async def issue_code(self, person_id: int) -> tuple[str, datetime.datetime]:
        """A link that starts the bot of the installation for this person, and when it stops working."""
        code = secrets.token_urlsafe(24)
        expires_at = datetime.datetime.now(datetime.UTC) + CODE_LIFETIME
        self.session.add(TelegramLinkCode(code=code, person_id=person_id, expires_at=expires_at))
        await self.session.commit()
        return f"https://t.me/{settings.TELEGRAM_BOT_USERNAME}?start={code}", expires_at

    async def unlink(self, person_id: int) -> None:
        await self.session.execute(delete(TelegramLink).where(TelegramLink.person_id == person_id))
        await self.session.commit()

    async def read_updates(self, gateway: TelegramGateway, *, wait_seconds: int = POLL_SECONDS) -> bool:
        """Read what the bot was told since the last time and act on it. False when another reader is at it.

        Telegram gives the updates of a bot to one reader, so the reading holds a lock for
        its transaction. The position moves in the same transaction as what the updates
        did: an update is not acted on twice, whatever stops the server.
        """
        got = await self.session.scalar(select(func.pg_try_advisory_xact_lock(func.hashtext("telegram.updates"))))
        if not got:
            await self.session.rollback()
            return False

        cursor = await self.session.scalar(select(TelegramCursor))
        try:
            updates = await gateway.get_updates(cursor.next_update_id if cursor else None, wait_seconds)
        except TelegramUnavailable:
            await self.session.rollback()
            raise

        replies: list[tuple[int, str]] = []
        for update in updates:
            match update.event:
                case Started(chat_id=chat_id, parameter=parameter):
                    linked = parameter is not None and await self._redeem(parameter, chat_id)
                    replies.append((chat_id, "linked" if linked else "invalid"))
                case Blocked(chat_id=chat_id):
                    await self.session.execute(delete(TelegramLink).where(TelegramLink.chat_id == chat_id))
                case None:
                    pass
        if updates:
            position = updates[-1].id + 1
            if cursor is None:
                self.session.add(TelegramCursor(next_update_id=position))
            else:
                cursor.next_update_id = position
        await self.session.commit()

        for chat_id, reply in replies:
            try:
                await gateway.send_message(chat_id, REPLIES[settings.UI_LOCALE][reply])
            except (TelegramUnavailable, ChatClosed):
                # The link is made or refused already; the person sees it in the service.
                continue
        return True

    async def _redeem(self, code: str, chat_id: int) -> bool:
        """Link the chat to the person the code was issued to. A code works once and until it expires."""
        found = await self.session.scalar(
            select(TelegramLinkCode).where(TelegramLinkCode.code == code).with_for_update()
        )
        if found is None or found.used_at is not None or found.expires_at <= datetime.datetime.now(datetime.UTC):
            return False
        found.used_at = func.now()
        await self.session.execute(
            insert(TelegramLink)
            .values(person_id=found.person_id, chat_id=chat_id)
            .on_conflict_do_update(index_elements=[TelegramLink.person_id], set_={"chat_id": chat_id})
        )
        return True
