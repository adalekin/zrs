"""Linking a person to their Telegram chat with a one-time link, and taking the link off."""

import asyncio
import datetime

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from internal.config import settings
from internal.service.telegram import TelegramUnavailable
from tests.conftest import FakeTelegram, Session, World, link_telegram, read_bot


@pytest.fixture
async def person(world: World) -> Session:
    return await world.sign_in("alice", "requester")


async def linked(person: Session) -> bool:
    return (await person.get("/v1/me")).json()["notifications"]["telegram_linked"]


async def code_of(person: Session) -> str:
    return (await person.post("/v1/telegram-link-codes")).json()["url"].split("start=")[1]


async def test_the_link_starts_the_bot_of_the_installation_with_a_code(person: Session) -> None:
    response = await person.post("/v1/telegram-link-codes")

    assert response.status_code == 201
    address, code = response.json()["url"].split("?start=")
    assert address == "https://t.me/zrs_test_bot"
    # Telegram takes up to 64 characters of letters, digits, underscores and hyphens.
    assert 16 <= len(code) <= 64 and code.replace("-", "").replace("_", "").isalnum()
    assert (await person.get("/v1/me")).json()["notifications"] == {"enabled": True, "telegram_linked": False}


async def test_starting_the_bot_by_the_link_links_the_chat(person: Session, telegram: FakeTelegram) -> None:
    telegram.start(77, await code_of(person))

    await read_bot(telegram)

    assert await linked(person)
    assert telegram.sent == [(77, "Telegram is linked. Messages about requests will come here.")]


async def test_a_link_works_once(world: World, person: Session, telegram: FakeTelegram) -> None:
    code = await code_of(person)
    telegram.start(77, code)
    await read_bot(telegram)
    telegram.sent.clear()

    telegram.start(88, code)
    await read_bot(telegram)

    assert telegram.sent == [(88, "The link is not valid. Get a new one on the notifications page of the service.")]
    stranger = await world.sign_in("mallory", "requester")
    assert not await linked(stranger)


async def test_a_link_stops_working_when_its_time_is_up(
    person: Session, telegram: FakeTelegram, engine: AsyncEngine
) -> None:
    telegram.start(77, await code_of(person))
    async with engine.begin() as connection:
        await connection.execute(
            text("UPDATE telegram_link_code SET expires_at = :then"),
            {"then": datetime.datetime.now(datetime.UTC) - datetime.timedelta(seconds=1)},
        )

    await read_bot(telegram)

    assert not await linked(person)
    assert telegram.sent[0][0] == 77 and "not valid" in telegram.sent[0][1]


@pytest.mark.parametrize("parameter", [None, "made-up-code"])
async def test_starting_the_bot_without_a_code_of_the_service_links_nothing(
    person: Session, telegram: FakeTelegram, parameter: str | None
) -> None:
    telegram.start(77, parameter)

    await read_bot(telegram)

    assert not await linked(person)
    assert "not valid" in telegram.sent[0][1]


async def test_a_new_link_moves_the_person_to_another_chat(person: Session, telegram: FakeTelegram) -> None:
    await link_telegram(person, telegram, 77)

    await link_telegram(person, telegram, 88)

    assert await linked(person)


async def test_the_person_unlinks_their_telegram(person: Session, telegram: FakeTelegram) -> None:
    await link_telegram(person, telegram, 77)

    response = await person.delete("/v1/telegram-link")

    assert response.status_code == 204
    assert not await linked(person)


async def test_blocking_the_bot_takes_the_link_off(person: Session, telegram: FakeTelegram) -> None:
    await link_telegram(person, telegram, 77)

    telegram.block(77)
    await read_bot(telegram)

    assert not await linked(person)


async def test_an_update_is_not_acted_on_twice(person: Session, telegram: FakeTelegram) -> None:
    await link_telegram(person, telegram, 77)
    await person.delete("/v1/telegram-link")

    # The same updates are still with Telegram; a restarted reader starts from its position.
    await read_bot(telegram)

    assert not await linked(person)
    assert telegram.sent == []


async def test_one_reader_at_a_time_listens_to_the_bot(person: Session, telegram: FakeTelegram) -> None:
    telegram.start(77, await code_of(person))
    telegram.hold = asyncio.Event()

    first = asyncio.create_task(read_bot(telegram))
    await asyncio.sleep(0.2)
    second = await read_bot(telegram)
    telegram.hold.set()

    assert second is False
    assert await first is True
    assert await linked(person)


async def test_a_reading_that_failed_is_done_again(person: Session, telegram: FakeTelegram) -> None:
    telegram.start(77, await code_of(person))
    telegram.available = False
    with pytest.raises(TelegramUnavailable):
        await read_bot(telegram)

    telegram.available = True
    await read_bot(telegram)

    assert await linked(person)


async def test_an_installation_without_notifications_offers_no_link(
    person: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "NOTIFICATIONS", "off")

    state = (await person.get("/v1/me")).json()["notifications"]
    asked = await person.post("/v1/telegram-link-codes")
    removed = await person.delete("/v1/telegram-link")

    assert state == {"enabled": False, "telegram_linked": False}
    assert asked.status_code == 409
    assert removed.status_code == 409
