"""The gateway to the Telegram Bot API, against a stand-in for Telegram."""

import httpx
import pytest
from pytest_httpx import HTTPXMock

from internal.service.telegram import Blocked, ChatClosed, Started, TelegramGateway, TelegramUnavailable, Update

BASE = "https://api.telegram.org/bot1234:test-token"


@pytest.fixture
def gateway() -> TelegramGateway:
    return TelegramGateway(token="1234:test-token", proxy_url=None)


async def test_a_message_is_sent_to_the_chat(gateway: TelegramGateway, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=f"{BASE}/sendMessage", json={"ok": True, "result": {"message_id": 1}})

    await gateway.send_message(77, "Request 5 waits for you")

    sent = httpx_mock.get_request()
    assert sent is not None
    assert sent.method == "POST"
    assert sent.read() and b'"chat_id":77' in sent.read()
    assert "Request 5 waits for you" in sent.read().decode()


@pytest.mark.parametrize("status", [429, 500, 502])
async def test_a_failure_on_the_side_of_telegram_may_be_repeated(
    gateway: TelegramGateway, httpx_mock: HTTPXMock, status: int
) -> None:
    httpx_mock.add_response(url=f"{BASE}/sendMessage", status_code=status, json={"ok": False, "description": "Later"})

    with pytest.raises(TelegramUnavailable):
        await gateway.send_message(77, "text")


async def test_a_broken_connection_may_be_repeated(gateway: TelegramGateway, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_exception(httpx.ConnectError("no route"), url=f"{BASE}/sendMessage")

    with pytest.raises(TelegramUnavailable):
        await gateway.send_message(77, "text")


async def test_a_failure_does_not_put_the_token_into_the_error(gateway: TelegramGateway, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_exception(httpx.ConnectError("no route"), url=f"{BASE}/sendMessage")

    with pytest.raises(TelegramUnavailable) as failure:
        await gateway.send_message(77, "text")

    assert "test-token" not in str(failure.value)


@pytest.mark.parametrize(
    ("status", "description"),
    [
        (403, "Forbidden: bot was blocked by the user"),
        (403, "Forbidden: user is deactivated"),
        (400, "Bad Request: chat not found"),
    ],
)
async def test_a_chat_that_takes_no_messages_is_told_apart(
    gateway: TelegramGateway, httpx_mock: HTTPXMock, status: int, description: str
) -> None:
    httpx_mock.add_response(
        url=f"{BASE}/sendMessage", status_code=status, json={"ok": False, "description": description}
    )

    with pytest.raises(ChatClosed):
        await gateway.send_message(77, "text")


async def test_updates_are_read_from_the_position(gateway: TelegramGateway, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=f"{BASE}/getUpdates",
        json={
            "ok": True,
            "result": [
                {"update_id": 10, "message": {"chat": {"id": 77, "type": "private"}, "text": "/start abc-DEF_1"}},
                {"update_id": 11, "message": {"chat": {"id": 78, "type": "private"}, "text": "/start"}},
                {"update_id": 12, "message": {"chat": {"id": 77, "type": "private"}, "text": "hello"}},
                {"update_id": 13, "message": {"chat": {"id": -5, "type": "group"}, "text": "/start abc"}},
                {
                    "update_id": 14,
                    "my_chat_member": {"chat": {"id": 77, "type": "private"}, "new_chat_member": {"status": "kicked"}},
                },
                {
                    "update_id": 15,
                    "my_chat_member": {"chat": {"id": 77, "type": "private"}, "new_chat_member": {"status": "member"}},
                },
            ],
        },
    )

    updates = await gateway.get_updates(offset=10, wait_seconds=0)

    assert updates == [
        Update(10, Started(77, "abc-DEF_1")),
        Update(11, Started(78, None)),
        Update(12, None),
        Update(13, None),
        Update(14, Blocked(77)),
        Update(15, None),
    ]
    asked = httpx_mock.get_request()
    assert asked is not None and b'"offset":10' in asked.read()


async def test_the_calls_go_through_the_proxy_of_the_installation(httpx_mock: HTTPXMock) -> None:
    through_proxy = TelegramGateway(token="1234:test-token", proxy_url="http://proxy.test:3128")
    httpx_mock.add_response(
        url=f"{BASE}/sendMessage", proxy_url="http://proxy.test:3128/", json={"ok": True, "result": {}}
    )

    await through_proxy.send_message(77, "text")

    assert len(httpx_mock.get_requests()) == 1
