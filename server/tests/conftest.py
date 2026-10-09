import asyncio
import datetime
import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from approck_fastapi_utils.exceptions import Unauthorized
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

BASE_DIR = Path(__file__).resolve().parents[1]

# The suite runs against the dedicated test database of the development PostgreSQL
# from the repository's compose.yaml. Settings are fixed here, not read from a .env file.
TEST_ENVIRONMENT = {
    "OIDC_ISSUER": "https://idp.test/realms/zrs",
    "OIDC_AUDIENCE": "zrs",
    "OIDC_ROLES_CLAIM": "roles",
    "ROLE_REQUESTER": "requester",
    "ROLE_MODERATOR": "moderator",
    "ROLE_FINANCE_DIRECTOR": "finance_director",
    "ROLE_PAYER": "payer",
    "CURRENCIES": "RUB,USD",
    "ATTACHMENT_MAX_BYTES": "1024",
    "TIMEZONE": "Europe/Moscow",
    "PAYMENT_DAY_ENDS_AT": "16:30",
    "NOTIFICATIONS": "telegram",
    "TELEGRAM_BOT_TOKEN": "1234:test-token",
    "TELEGRAM_BOT_USERNAME": "zrs_test_bot",
    "TELEGRAM_EGRESS": "direct",
    "TELEGRAM_PROXY_URL": "",
    "AUTH_ORIGIN": "https://zrs.test",
    "UI_LOCALE": "en",
    "S3_ENDPOINT_URL": "https://storage.test",
    "S3_BUCKET": "zrs",
    "S3_ACCESS_KEY_ID": "test",
    "S3_SECRET_ACCESS_KEY": "test",
    "S3_REGION": "us-east-1",
    "DB_HOST": os.environ.get("TEST_DB_HOST", "127.0.0.1"),
    "DB_PORT": os.environ.get("TEST_DB_PORT", "54320"),
    "DB_USER": os.environ.get("TEST_DB_USER", "zrs"),
    "DB_PASSWORD": os.environ.get("TEST_DB_PASSWORD", "zrs"),
    "DB_NAME": os.environ.get("TEST_DB_NAME", "zrs_test"),
}
os.environ.update(TEST_ENVIRONMENT)

import approck_sqlalchemy_utils.session
from httpx import ASGITransport, AsyncClient, Response

from internal.app.http.app import create_app
from internal.config import settings
from internal.controller.http.deps import get_storage, get_today, get_verifier
from internal.exceptions import IdentityProviderUnavailable
from internal.service.notification import NotificationService
from internal.service.telegram import Blocked, ChatClosed, Started, TelegramUnavailable, Update
from internal.service.telegram_link import TelegramLinkService

TEST_DATABASE_URL = settings.database_url.render_as_string(hide_password=False)

if not make_url(TEST_DATABASE_URL).database.endswith("_test"):
    raise RuntimeError("The test suite rebuilds its database and refuses to run on one not named *_test")


def _rebuild_schema() -> None:
    async def reset() -> None:
        engine = create_async_engine(TEST_DATABASE_URL)
        async with engine.begin() as connection:
            await connection.execute(text("DROP SCHEMA public CASCADE"))
            await connection.execute(text("CREATE SCHEMA public"))
        await engine.dispose()

    asyncio.run(reset())

    config = Config(str(BASE_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BASE_DIR / "migrations"))
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.upgrade(config, "head")


@pytest.fixture(scope="session", autouse=True)
def migrated_schema() -> Iterator[None]:
    _rebuild_schema()
    yield


@pytest_asyncio.fixture(scope="session")
async def engine(migrated_schema: None) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(TEST_DATABASE_URL)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def clean_tables(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "TRUNCATE notification, telegram_link, telegram_link_code, telegram_cursor, "
                "payment, attachment, journal_entry, expense_request, reference_item, person "
                "RESTART IDENTITY CASCADE"
            )
        )


class FakeVerifier:
    """Stands in for the provider: a token is valid when it was issued through ``issue``."""

    def __init__(self) -> None:
        self._tokens: dict[str, dict[str, Any]] = {}
        self._userinfo: dict[str, dict[str, Any]] = {}
        self.userinfo_available = True
        self.userinfo_calls = 0
        self._issued = 0

    def issue(self, sub: str, name: str | None, roles: list[str], email: str | None = None) -> str:
        self._issued += 1
        token = f"token-{sub}-{self._issued}"
        issued_at = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC) + datetime.timedelta(minutes=self._issued)
        self._tokens[token] = {"sub": sub, "iat": int(issued_at.timestamp()), "roles": roles}
        self._userinfo[token] = {"sub": sub, "email": email or f"{sub}@example.test"}
        if name is not None:
            self._userinfo[token]["name"] = name
        return token

    async def verify(self, token: str) -> dict[str, Any]:
        try:
            return self._tokens[token]
        except KeyError as exc:
            raise Unauthorized("Invalid token") from exc

    async def userinfo(self, token: str) -> dict[str, Any]:
        self.userinfo_calls += 1
        if not self.userinfo_available:
            raise IdentityProviderUnavailable("The identity provider is unavailable")
        return self._userinfo[token]


class FakeStorage:
    """In-memory stand-in for the S3-compatible store."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def upload_from_bytes(self, key: str, body: bytes, content_type: str | None = None) -> None:
        self.objects[key] = body

    async def download(self, key: str) -> bytes:
        return self.objects[key]

    async def delete(self, key: str) -> None:
        del self.objects[key]


@pytest.fixture
def verifier() -> FakeVerifier:
    return FakeVerifier()


@pytest.fixture
def storage() -> FakeStorage:
    return FakeStorage()


class FakeTelegram:
    """Stands in for the gateway to the Bot API: keeps what was sent and hands out the updates a test put in."""

    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []
        self.updates: list[Update] = []
        self.available = True
        #: Chats whose people blocked the bot.
        self.closed: set[int] = set()
        #: Set by a test to keep a reader inside its call.
        self.hold: asyncio.Event | None = None

    async def send_message(self, chat_id: int, text: str) -> None:
        if not self.available:
            raise TelegramUnavailable("Telegram is unavailable")
        if chat_id in self.closed:
            raise ChatClosed("Forbidden: bot was blocked by the user")
        self.sent.append((chat_id, text))

    async def get_updates(self, offset: int | None, wait_seconds: int) -> list[Update]:
        if not self.available:
            raise TelegramUnavailable("Telegram is unavailable")
        if self.hold is not None:
            await self.hold.wait()
        return [update for update in self.updates if offset is None or update.id >= offset]

    def start(self, chat_id: int, parameter: str | None) -> None:
        """A person starts the bot in their chat."""
        self.updates.append(Update(len(self.updates) + 100, Started(chat_id, parameter)))

    def block(self, chat_id: int) -> None:
        """A person blocks the bot."""
        self.closed.add(chat_id)
        self.updates.append(Update(len(self.updates) + 100, Blocked(chat_id)))


@pytest.fixture
def telegram() -> FakeTelegram:
    return FakeTelegram()


class Clock:
    """The calendar day of the installation, set by a test."""

    def __init__(self) -> None:
        # A Friday.
        self.today = datetime.date(2026, 10, 9)


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest_asyncio.fixture
async def client(verifier: FakeVerifier, storage: FakeStorage, clock: Clock) -> AsyncIterator[AsyncClient]:
    app = create_app()
    app.dependency_overrides[get_verifier] = lambda: verifier
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_today] = lambda: clock.today
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
        yield http_client


class Session:
    """One person's signed-in session: sends requests with their token."""

    def __init__(self, client: AsyncClient, token: str, person_id: int) -> None:
        self._client = client
        self.token = token
        self.id = person_id

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    async def get(self, url: str, **kwargs: Any) -> Response:
        return await self._client.get(url, headers=self.headers, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> Response:
        return await self._client.post(url, headers=self.headers, **kwargs)

    async def patch(self, url: str, **kwargs: Any) -> Response:
        return await self._client.patch(url, headers=self.headers, **kwargs)

    async def delete(self, url: str, **kwargs: Any) -> Response:
        return await self._client.delete(url, headers=self.headers, **kwargs)


class World:
    """Test helper: signs people in and builds requests through the public API only."""

    def __init__(self, client: AsyncClient, verifier: FakeVerifier) -> None:
        self.client = client
        self.verifier = verifier

    async def sign_in(self, sub: str, *roles: str, name: str | None = None) -> Session:
        token = self.verifier.issue(sub, name or sub.title(), list(roles))
        response = await self.client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200, response.text
        return Session(self.client, token, response.json()["id"])

    async def reference_item(self, kind: str, name: str) -> dict[str, Any]:
        director = await self.sign_in("setup-director", "finance_director")
        response = await director.post("/v1/reference-items", json={"kind": kind, "name": name})
        assert response.status_code == 201, response.text
        return response.json()

    async def reference_lists(self) -> dict[str, int]:
        return {
            "operation_type_id": (await self.reference_item("operation_type", "Advertising"))["id"],
            "priority_id": (await self.reference_item("priority", "Normal"))["id"],
            "payment_form_id": (await self.reference_item("payment_form", "Card"))["id"],
        }

    def request_body(self, lists: dict[str, int], moderator: Session, **overrides: Any) -> dict[str, Any]:
        body: dict[str, Any] = {
            "operation_type_id": lists["operation_type_id"],
            "priority_id": lists["priority_id"],
            "moderator_id": moderator.id,
            "situation": "Monthly subscription for the video tool",
            "solution": "Pay 1590 by card, the accountant sends the card details",
            "amount": "1590.00",
            "currency": "RUB",
            "payment_period": "monthly",
        }
        body.update(overrides)
        return body

    async def submit(
        self, author: Session, lists: dict[str, int], moderator: Session, **overrides: Any
    ) -> dict[str, Any]:
        response = await author.post("/v1/requests", json=self.request_body(lists, moderator, **overrides))
        assert response.status_code == 201, response.text
        return response.json()


@pytest.fixture
def world(client: AsyncClient, verifier: FakeVerifier) -> World:
    return World(client, verifier)


async def read_bot(telegram: FakeTelegram) -> bool:
    """One reading of what the bot was told, as the background task does it."""
    async with approck_sqlalchemy_utils.session.context_session() as session:
        return await TelegramLinkService(session).read_updates(telegram, wait_seconds=0)  # type: ignore[arg-type]


async def link_telegram(person: Session, telegram: FakeTelegram, chat_id: int) -> None:
    """The person gets a link in the service and starts the bot with it."""
    response = await person.post("/v1/telegram-link-codes")
    assert response.status_code == 201, response.text
    telegram.start(chat_id, response.json()["url"].split("start=")[1])
    assert await read_bot(telegram)
    telegram.sent.clear()


async def send_waiting(telegram: FakeTelegram, today: datetime.date) -> None:
    """One pass of the sender, as the background task does it."""
    async with approck_sqlalchemy_utils.session.context_session() as session:
        notifications = NotificationService(session)
        await notifications.announce_new_periods(today)
        while await notifications.send_next(telegram, today):  # type: ignore[arg-type]
            pass
