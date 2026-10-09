"""The gateway to the Telegram Bot API, against a stand-in for Telegram."""

import json

import httpx
import pytest
from pytest_httpx import HTTPXMock

from internal.service.telegram import (
    Blocked,
    Button,
    ChatClosed,
    Pressed,
    Said,
    Started,
    TelegramGateway,
    TelegramUnavailable,
    Update,
)

BASE = "https://api.telegram.org/bot1234:test-token"


@pytest.fixture
def gateway() -> TelegramGateway:
    return TelegramGateway(token="1234:test-token", proxy_url=None)


async def test_a_message_is_sent_to_the_chat(gateway: TelegramGateway, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=f"{BASE}/sendMessage", json={"ok": True, "result": {"message_id": 41}})

    number = await gateway.send_message(77, "<b>Request 5</b> waits for you")

    sent = httpx_mock.get_request()
    assert sent is not None and sent.method == "POST"
    assert json.loads(sent.read()) == {
        "chat_id": 77,
        "text": "<b>Request 5</b> waits for you",
        "parse_mode": "HTML",
        "link_preview_options": {"is_disabled": True},
    }
    assert number == 41


async def test_a_message_carries_buttons_and_answers_an_earlier_one(
    gateway: TelegramGateway, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(url=f"{BASE}/sendMessage", json={"ok": True, "result": {"message_id": 42}})

    await gateway.send_message(
        77, "text", [[Button("Approve", "t1"), Button("Reject", "t2")], [Button("Return", "t3")]], reply_to=41
    )

    sent = json.loads(httpx_mock.get_request().read())  # type: ignore[union-attr]
    assert sent["reply_markup"] == {
        "inline_keyboard": [
            [{"text": "Approve", "callback_data": "t1"}, {"text": "Reject", "callback_data": "t2"}],
            [{"text": "Return", "callback_data": "t3"}],
        ]
    }
    assert sent["reply_parameters"] == {"message_id": 41, "allow_sending_without_reply": True}


async def test_a_press_is_answered_and_the_buttons_are_taken_off(
    gateway: TelegramGateway, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(url=f"{BASE}/answerCallbackQuery", json={"ok": True, "result": True})
    httpx_mock.add_response(url=f"{BASE}/editMessageReplyMarkup", json={"ok": True, "result": {"message_id": 42}})

    await gateway.answer_press("press-1", "Request 5 is approved")
    await gateway.set_keyboard(77, 42, None)

    answered, edited = (json.loads(request.read()) for request in httpx_mock.get_requests())
    assert answered == {"callback_query_id": "press-1", "text": "Request 5 is approved"}
    assert edited == {"chat_id": 77, "message_id": 42, "reply_markup": {"inline_keyboard": []}}


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
                {
                    "update_id": 16,
                    "callback_query": {
                        "id": "press-9",
                        "data": "token:skip",
                        "message": {"message_id": 42, "chat": {"id": 77, "type": "private"}},
                    },
                },
                {"update_id": 17, "callback_query": {"id": "press-10", "data": "token"}},
            ],
        },
    )

    updates = await gateway.get_updates(offset=10, wait_seconds=0)

    assert updates == [
        Update(10, Started(77, "abc-DEF_1")),
        Update(11, Started(78, None)),
        Update(12, Said(77, "hello")),
        Update(13, None),
        Update(14, Blocked(77)),
        Update(15, None),
        Update(16, Pressed(77, 42, "press-9", "token:skip")),
        # A press that came without its message is of no use.
        Update(17, None),
    ]
    asked = httpx_mock.get_request()
    assert asked is not None and b'"offset":10' in asked.read()


async def test_the_calls_go_through_the_proxy_of_the_installation(httpx_mock: HTTPXMock) -> None:
    through_proxy = TelegramGateway(token="1234:test-token", proxy_url="http://proxy.test:3128")
    httpx_mock.add_response(
        url=f"{BASE}/sendMessage", proxy_url="http://proxy.test:3128/", json={"ok": True, "result": {"message_id": 1}}
    )

    await through_proxy.send_message(77, "text")

    assert len(httpx_mock.get_requests()) == 1
