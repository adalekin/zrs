import datetime
import secrets

from approck_services.base import BaseService
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from internal.config import settings
from internal.entity.notification import TelegramLink, TelegramLinkCode

#: How long a link that starts the bot works.
CODE_LIFETIME = datetime.timedelta(minutes=15)


class TelegramLinkService(BaseService):
    """Links a person to their Telegram chat with a one-time code."""

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

    async def unlink_chat(self, chat_id: int) -> None:
        """Take the link off a chat whose person blocked the bot. The caller owns the transaction."""
        await self.session.execute(delete(TelegramLink).where(TelegramLink.chat_id == chat_id))

    async def links(self, person_id: int, chat_id: int) -> bool:
        """Whether this chat is the one the person gets messages in."""
        found = await self.session.scalar(
            select(TelegramLink.id).where(TelegramLink.person_id == person_id, TelegramLink.chat_id == chat_id)
        )
        return found is not None

    async def person_of(self, chat_id: int) -> int | None:
        return await self.session.scalar(select(TelegramLink.person_id).where(TelegramLink.chat_id == chat_id))

    async def redeem(self, code: str, chat_id: int) -> bool:
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
