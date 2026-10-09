"""The work the server does besides answering requests: sending messages and listening to the bot.

Both run as tasks of the server's own event loop, started only when the installation
sends notifications. Several replicas may run them: a waiting message is locked by the
replica that sends it, and one replica at a time reads what the bot is told.
"""

import asyncio
import contextlib
import datetime
from collections.abc import AsyncIterator, Awaitable, Callable

import approck_sqlalchemy_utils.session
from fastapi import FastAPI
from loguru import logger
from sqlalchemy.exc import SQLAlchemyError

from internal.config import settings
from internal.service.bot import BotListener
from internal.service.notification import NotificationService
from internal.service.telegram import TelegramGateway, TelegramUnavailable

#: How long the sender rests when no message waits, and after Telegram failed.
SEND_PAUSE_SECONDS = 5.0
#: How long a task rests after a pass that failed, so that a dead network is not hammered.
FAILURE_PAUSE_SECONDS = 10.0
#: How long a replica that is not the reader waits before it asks for the turn again.
READER_PAUSE_SECONDS = 15.0


def today() -> datetime.date:
    return datetime.datetime.now(settings.TIMEZONE).date()


async def send_waiting(gateway: TelegramGateway) -> None:
    """One pass of the sender: the messages of a new period first, then everything that waits."""
    async with approck_sqlalchemy_utils.session.context_session() as session:
        notifications = NotificationService(session)
        await notifications.announce_new_periods(today())
        while await notifications.send_next(gateway, today()):
            pass


async def read_updates(gateway: TelegramGateway) -> None:
    """One long poll of the bot. A replica that did not get the turn rests before it asks again."""
    async with approck_sqlalchemy_utils.session.context_session() as session:
        if not await BotListener(session).read_updates(gateway, today()):
            await asyncio.sleep(READER_PAUSE_SECONDS)


async def forever(step: Callable[[], Awaitable[None]], *, pause: float) -> None:
    while True:
        try:
            await step()
        except TelegramUnavailable:
            # Logged by the gateway. The messages wait in the database for the next pass.
            await asyncio.sleep(FAILURE_PAUSE_SECONDS)
        except (SQLAlchemyError, OSError):
            # The database or the network gave way for a moment: the next pass starts afresh.
            logger.exception("A background pass failed")
            await asyncio.sleep(FAILURE_PAUSE_SECONDS)
        await asyncio.sleep(pause)


def report_stopped(task: asyncio.Task[None]) -> None:
    """Say loudly that a background task is gone: the messages wait until the server is restarted."""
    if not task.cancelled() and task.exception() is not None:
        logger.opt(exception=task.exception()).critical("The background task {} stopped", task.get_name())


@contextlib.asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if settings.NOTIFICATIONS != "telegram":
        yield
        return

    gateway = TelegramGateway(token=settings.TELEGRAM_BOT_TOKEN, proxy_url=settings.TELEGRAM_PROXY_URL)
    tasks = [
        asyncio.create_task(
            forever(lambda: send_waiting(gateway), pause=SEND_PAUSE_SECONDS), name="send-notifications"
        ),
        asyncio.create_task(forever(lambda: read_updates(gateway), pause=0.0), name="read-telegram-updates"),
    ]
    for task in tasks:
        task.add_done_callback(report_stopped)
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
