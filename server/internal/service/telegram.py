"""The Telegram Bot API as the service uses it: send a message, read what the bot was told."""

from dataclasses import dataclass
from typing import Any

import httpx
from loguru import logger

API_URL = "https://api.telegram.org"
#: How long a call that is not a long poll may take.
CALL_TIMEOUT_SECONDS = 10.0


class TelegramUnavailable(Exception):
    """The call did not get through or Telegram could not serve it now. It may be repeated later."""


class ChatClosed(Exception):
    """Telegram will not deliver to this chat: the person blocked the bot or the chat is gone."""


@dataclass(frozen=True)
class Started:
    """A person started the bot, with the parameter of the link they followed if there was one."""

    chat_id: int
    parameter: str | None


@dataclass(frozen=True)
class Blocked:
    """A person blocked the bot in their chat with it."""

    chat_id: int


@dataclass(frozen=True)
class Pressed:
    """A person pressed a button under a message of the bot."""

    chat_id: int
    message_id: int
    #: What Telegram wants answered, so that the button stops spinning.
    press_id: str
    #: What the button carries.
    data: str


@dataclass(frozen=True)
class Said:
    """A person wrote to the bot in their chat with it."""

    chat_id: int
    text: str


Event = Started | Blocked | Pressed | Said


@dataclass(frozen=True)
class Button:
    text: str
    #: What the bot gets back when the button is pressed: 1 to 64 bytes.
    data: str


#: Rows of buttons under a message.
Keyboard = list[list[Button]]


@dataclass(frozen=True)
class Update:
    id: int
    #: What the update says, when the service has a use for it.
    event: Event | None


class TelegramGateway:
    """Gateway to the Bot API of one bot. Nothing else in the service knows the API."""

    def __init__(self, token: str, proxy_url: str | None) -> None:
        self._base_url = f"{API_URL}/bot{token}"
        self._proxy_url = proxy_url

    async def send_message(
        self, chat_id: int, text: str, keyboard: Keyboard | None = None, *, reply_to: int | None = None
    ) -> int:
        """Send a message written in Telegram HTML, with buttons under it when given.

        ``reply_to`` ties the message to an earlier one of the chat, so that an answer stands
        next to what it answers. Returns the number of the message in the chat.
        """
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": True},
        }
        if keyboard:
            payload["reply_markup"] = self._markup(keyboard)
        if reply_to is not None:
            # The message it answers may be gone: the answer is sent all the same.
            payload["reply_parameters"] = {"message_id": reply_to, "allow_sending_without_reply": True}
        sent = await self._call("sendMessage", payload, timeout=CALL_TIMEOUT_SECONDS)
        return sent["message_id"]

    async def answer_press(self, press_id: str, text: str) -> None:
        """Tell the person who pressed a button what came of it, as a notice over the chat."""
        await self._call(
            "answerCallbackQuery", {"callback_query_id": press_id, "text": text}, timeout=CALL_TIMEOUT_SECONDS
        )

    async def set_keyboard(self, chat_id: int, message_id: int, keyboard: Keyboard | None) -> None:
        """Replace the buttons under a message, or take them off."""
        await self._call(
            "editMessageReplyMarkup",
            {"chat_id": chat_id, "message_id": message_id, "reply_markup": self._markup(keyboard or [])},
            timeout=CALL_TIMEOUT_SECONDS,
        )

    async def get_updates(self, offset: int | None, wait_seconds: int) -> list[Update]:
        """Updates from ``offset`` on, waiting up to ``wait_seconds`` for the first one."""
        payload: dict[str, Any] = {
            "timeout": wait_seconds,
            "allowed_updates": ["message", "my_chat_member", "callback_query"],
        }
        if offset is not None:
            payload["offset"] = offset
        result = await self._call("getUpdates", payload, timeout=wait_seconds + CALL_TIMEOUT_SECONDS)
        return [Update(id=raw["update_id"], event=self._event(raw)) for raw in result]

    async def _call(self, method: str, payload: dict[str, Any], *, timeout: float) -> Any:
        try:
            async with httpx.AsyncClient(proxy=self._proxy_url, timeout=timeout) as client:
                response = await client.post(f"{self._base_url}/{method}", json=payload)
                body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            # The address carries the token of the bot: the log gets the method alone.
            logger.warning("Telegram call {} failed: {}", method, type(exc).__name__)
            raise TelegramUnavailable(f"Telegram call {method} failed") from exc

        if body.get("ok") is True:
            return body["result"]

        description = str(body.get("description", ""))
        if response.status_code == 403 or (response.status_code == 400 and "chat not found" in description):
            raise ChatClosed(description)
        logger.warning("Telegram refused {}: {} {}", method, response.status_code, description)
        raise TelegramUnavailable(f"Telegram refused {method}: {response.status_code}")

    @staticmethod
    def _markup(keyboard: Keyboard) -> dict[str, Any]:
        return {
            "inline_keyboard": [
                [{"text": button.text, "callback_data": button.data} for button in row] for row in keyboard
            ]
        }

    @staticmethod
    def _event(raw: dict[str, Any]) -> Event | None:
        message = raw.get("message")
        if message is not None and message["chat"]["type"] == "private":
            text = str(message.get("text", ""))
            words = text.split(maxsplit=1)
            if words and words[0] == "/start":
                return Started(chat_id=message["chat"]["id"], parameter=words[1] if len(words) > 1 else None)
            return Said(chat_id=message["chat"]["id"], text=text) if text.strip() else None

        press = raw.get("callback_query")
        if press is not None:
            under = press.get("message")
            if under is None or under["chat"]["type"] != "private" or "data" not in press:
                return None
            return Pressed(
                chat_id=under["chat"]["id"], message_id=under["message_id"], press_id=press["id"], data=press["data"]
            )

        membership = raw.get("my_chat_member")
        if (
            membership is not None
            and membership["chat"]["type"] == "private"
            and membership["new_chat_member"]["status"] == "kicked"
        ):
            return Blocked(chat_id=membership["chat"]["id"])
        return None
