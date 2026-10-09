"""Decisions on requests taken with the buttons under the messages of the bot."""

import html
import re
from dataclasses import dataclass
from typing import Any

import pytest

from internal.config import settings
from tests.conftest import Clock, FakeTelegram, Session, World, link_telegram, read_bot, send_waiting

AUTHOR, MODERATOR, DIRECTOR, PAYER = 1, 2, 3, 4


def plain(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", text))


@dataclass
class Cast:
    world: World
    clock: Clock
    telegram: FakeTelegram
    lists: dict[str, int]
    author: Session
    moderator: Session
    director: Session
    payer: Session

    async def submit(self, **overrides: Any) -> dict[str, Any]:
        return await self.world.submit(self.author, self.lists, self.moderator, **overrides)

    async def read(self, request: dict[str, Any]) -> dict[str, Any]:
        return (await self.director.get(f"/v1/requests/{request['id']}")).json()

    async def deliver(self) -> None:
        await send_waiting(self.telegram, self.clock.today)

    async def message_to(self, chat: int) -> int:
        """Send what waits and give the number of the latest message with buttons in this chat."""
        await self.deliver()
        return max(number for number in self.telegram.keyboards if self.telegram.chat_of[number] == chat)

    async def press(self, chat: int, message: int, label: str) -> None:
        self.telegram.press(chat, message, self.telegram.buttons(message)[label])
        await read_bot(self.telegram, self.clock.today)

    async def say(self, chat: int, text: str) -> None:
        self.telegram.say(chat, text)
        await read_bot(self.telegram, self.clock.today)

    def last(self, chat: int) -> str:
        """The latest message of the bot in a chat, as a person reads it."""
        return plain(next(text for to, text in reversed(self.telegram.sent) if to == chat))


@pytest.fixture
async def cast(world: World, clock: Clock, telegram: FakeTelegram) -> Cast:
    people = {
        "author": await world.sign_in("author", "requester", name="Alice Author"),
        "moderator": await world.sign_in("moderator", "moderator", name="Bob Moderator"),
        "director": await world.sign_in("director", "finance_director", name="Carol Director"),
        "payer": await world.sign_in("payer", "payer", name="Dave Payer"),
    }
    lists = await world.reference_lists()
    for chat, person in zip((AUTHOR, MODERATOR, DIRECTOR, PAYER), people.values(), strict=True):
        await link_telegram(person, telegram, chat)
    return Cast(world=world, clock=clock, telegram=telegram, lists=lists, **people)


# --- the buttons a message carries ---


async def test_the_moderator_is_offered_four_decisions(cast: Cast) -> None:
    await cast.submit()

    message = await cast.message_to(MODERATOR)

    assert list(cast.telegram.buttons(message)) == ["Approve", "To the director", "Return", "Reject"]
    assert [len(row) for row in cast.telegram.keyboards[message]] == [2, 2]


async def test_the_finance_director_is_offered_three_decisions(cast: Cast) -> None:
    request = await cast.submit()
    await cast.moderator.post(f"/v1/requests/{request['id']}/escalate", json={})

    message = await cast.message_to(DIRECTOR)

    assert list(cast.telegram.buttons(message)) == ["Approve", "Return", "Reject"]


async def test_the_payer_and_the_author_get_no_buttons(cast: Cast) -> None:
    approved = await cast.submit()
    returned = await cast.submit()
    await cast.deliver()
    cast.telegram.keyboards.clear()

    await cast.moderator.post(f"/v1/requests/{approved['id']}/approve", json={})
    await cast.moderator.post(f"/v1/requests/{returned['id']}/return", json={})
    await cast.deliver()

    assert cast.telegram.keyboards == {}
    assert {to for to, _ in cast.telegram.sent[-3:]} == {AUTHOR, PAYER}


async def test_an_installation_that_forbids_decisions_sends_no_buttons(
    cast: Cast, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "TELEGRAM_DECISIONS", "off")

    await cast.submit()
    await cast.deliver()

    assert cast.telegram.keyboards == {}
    assert "waits for your decision" in cast.last(MODERATOR)
    assert (await cast.moderator.get("/v1/me")).json()["notifications"]["telegram_decisions"] is False


async def test_a_button_carries_a_token_and_nothing_of_the_request(cast: Cast) -> None:
    request = await cast.submit()

    message = await cast.message_to(MODERATOR)

    for data in cast.telegram.buttons(message).values():
        assert 16 <= len(data.encode()) <= 64
        assert str(request["id"]) != data and "approve" not in data


# --- a decision by one press ---


async def test_the_moderator_approves_with_a_button(cast: Cast) -> None:
    request = await cast.submit()
    message = await cast.message_to(MODERATOR)

    await cast.press(MODERATOR, message, "Approve")

    decided = await cast.read(request)
    assert decided["status"] == "approved"
    assert decided["journal"][-1]["person"]["id"] == cast.moderator.id
    assert cast.telegram.answers == [f"Request No. {request['id']} is approved. The author will get a message."]
    assert cast.last(MODERATOR) == f"Request No. {request['id']} is approved. The author will get a message."
    # The answer stands by the message it answers, and the buttons under that message are gone.
    assert cast.telegram.replies[cast.telegram.latest] == message
    assert message not in cast.telegram.keyboards


async def test_a_decision_from_telegram_is_told_like_one_from_the_service(cast: Cast) -> None:
    request = await cast.submit()
    message = await cast.message_to(MODERATOR)

    await cast.press(MODERATOR, message, "Approve")
    cast.telegram.sent.clear()
    await cast.deliver()

    assert sorted((to, plain(text).split("\n", 1)[0]) for to, text in cast.telegram.sent) == [
        (AUTHOR, f"🟢 Your request No. {request['id']} is approved"),
        (PAYER, f"🟢 Request No. {request['id']} is approved and waits for payment"),
    ]


async def test_the_moderator_passes_the_request_to_the_finance_director(cast: Cast) -> None:
    request = await cast.submit()
    message = await cast.message_to(MODERATOR)

    await cast.press(MODERATOR, message, "To the director")

    assert (await cast.read(request))["status"] == "escalated"
    assert cast.last(MODERATOR).startswith(f"Request No. {request['id']} is passed to the finance director")


async def test_a_request_decided_elsewhere_is_left_as_it_is(cast: Cast) -> None:
    request = await cast.submit()
    message = await cast.message_to(MODERATOR)
    await cast.author.post(f"/v1/requests/{request['id']}/cancel", json={})

    await cast.press(MODERATOR, message, "Approve")

    assert (await cast.read(request))["status"] == "rejected"
    assert cast.telegram.answers == [f"Request No. {request['id']} is already in the status 'Rejected'"]
    assert message not in cast.telegram.keyboards


async def test_a_button_pressed_twice_decides_once(cast: Cast) -> None:
    request = await cast.submit()
    message = await cast.message_to(MODERATOR)
    approve = cast.telegram.buttons(message)["Approve"]

    cast.telegram.press(MODERATOR, message, approve)
    cast.telegram.press(MODERATOR, message, approve)
    await read_bot(cast.telegram, cast.clock.today)

    journal = (await cast.read(request))["journal"]
    assert [entry["status"] for entry in journal] == ["new", "approved"]
    assert cast.telegram.answers == [
        f"Request No. {request['id']} is approved. The author will get a message.",
        f"Request No. {request['id']} is already in the status 'Approved'",
    ]


async def test_a_chat_that_was_unlinked_decides_nothing(cast: Cast) -> None:
    request = await cast.submit()
    message = await cast.message_to(MODERATOR)
    approve = cast.telegram.buttons(message)["Approve"]
    await cast.moderator.delete("/v1/telegram-link")

    cast.telegram.press(MODERATOR, message, approve)
    await read_bot(cast.telegram, cast.clock.today)

    assert (await cast.read(request))["status"] == "new"
    assert cast.telegram.answers == ["This chat is not linked to the service"]
    assert message not in cast.telegram.keyboards


async def test_a_button_pressed_from_another_chat_decides_nothing(cast: Cast) -> None:
    request = await cast.submit()
    message = await cast.message_to(MODERATOR)

    cast.telegram.press(PAYER, message, cast.telegram.buttons(message)["Approve"])
    cast.telegram.press(MODERATOR, message, "made-up-token")
    await read_bot(cast.telegram, cast.clock.today)

    assert (await cast.read(request))["status"] == "new"
    assert cast.telegram.answers == ["The button does not work any more"] * 2


# --- a return and a rejection ask for the reason ---


async def test_a_rejection_takes_the_reason_from_the_next_message(cast: Cast) -> None:
    request = await cast.submit()
    await cast.moderator.post(f"/v1/requests/{request['id']}/escalate", json={})
    message = await cast.message_to(DIRECTOR)

    await cast.press(DIRECTOR, message, "Reject")
    asked = cast.last(DIRECTOR), (await cast.read(request))["status"]
    await cast.say(DIRECTOR, "  No budget for it this quarter  ")

    assert asked == (f"Why is request No. {request['id']} rejected? Write it in a reply.", "escalated")
    rejected = await cast.read(request)
    assert rejected["status"] == "rejected"
    assert rejected["journal"][-1]["comment"] == "No budget for it this quarter"
    assert (rejected["rejected_by"]["id"], rejected["rejected_as"]) == (cast.director.id, "finance_director")
    assert cast.last(DIRECTOR) == f"Request No. {request['id']} is rejected. The author will get a message."
    # Neither the buttons of the decisions nor the two under the question are left to press.
    assert cast.telegram.keyboards == {}


async def test_the_author_is_told_the_reason_given_in_telegram(cast: Cast) -> None:
    request = await cast.submit()
    message = await cast.message_to(MODERATOR)
    await cast.press(MODERATOR, message, "Reject")
    await cast.say(MODERATOR, "Not needed any more")
    cast.telegram.sent.clear()

    await cast.deliver()

    assert [plain(text) for to, text in cast.telegram.sent if to == AUTHOR] == [
        (
            f"⚫ Your request No. {request['id']} is rejected\n"
            "Monthly subscription for the video tool\n"
            "Rejected by the moderator Bob Moderator\n"
            "Not needed any more"
        )
    ]


async def test_a_return_may_go_without_a_comment(cast: Cast) -> None:
    request = await cast.submit()
    message = await cast.message_to(MODERATOR)

    await cast.press(MODERATOR, message, "Return")
    question = cast.telegram.latest
    await cast.press(MODERATOR, question, "Without a comment")

    returned = await cast.read(request)
    assert returned["status"] == "returned"
    assert returned["journal"][-1]["comment"] is None
    assert question not in cast.telegram.keyboards and message not in cast.telegram.keyboards


async def test_a_cancelled_decision_leaves_the_buttons(cast: Cast) -> None:
    request = await cast.submit()
    message = await cast.message_to(MODERATOR)

    await cast.press(MODERATOR, message, "Reject")
    question = cast.telegram.latest
    await cast.press(MODERATOR, question, "Cancel")
    await cast.say(MODERATOR, "This is no reason any more")

    assert (await cast.read(request))["status"] == "new"
    assert question not in cast.telegram.keyboards
    assert list(cast.telegram.buttons(message)) == ["Approve", "To the director", "Return", "Reject"]
    assert cast.last(MODERATOR).startswith("I write about requests")


async def test_another_button_takes_the_question_about_the_reason_back(cast: Cast) -> None:
    first = await cast.submit()
    first_message = await cast.message_to(MODERATOR)
    second = await cast.submit()
    second_message = await cast.message_to(MODERATOR)

    await cast.press(MODERATOR, first_message, "Reject")
    await cast.press(MODERATOR, second_message, "Approve")
    await cast.say(MODERATOR, "A message that is no reason")

    assert (await cast.read(first))["status"] == "new"
    assert (await cast.read(second))["status"] == "approved"
    assert cast.last(MODERATOR).startswith("I write about requests")


async def test_a_message_nobody_asked_for_does_nothing(cast: Cast) -> None:
    request = await cast.submit()
    await cast.deliver()

    await cast.say(MODERATOR, "approve it please")

    assert (await cast.read(request))["status"] == "new"
    assert cast.last(MODERATOR).startswith("I write about requests")


async def test_the_question_about_the_reason_outlives_a_restart(cast: Cast) -> None:
    request = await cast.submit()
    message = await cast.message_to(MODERATOR)
    await cast.press(MODERATOR, message, "Return")

    # Another reading, as after a restart of the server or on another replica: nothing is kept in memory.
    await read_bot(cast.telegram, cast.clock.today)
    await cast.say(MODERATOR, "Attach the invoice")

    returned = await cast.read(request)
    assert (returned["status"], returned["journal"][-1]["comment"]) == ("returned", "Attach the invoice")


# --- whose rights a decision is taken with ---


async def test_a_person_who_signed_in_without_the_role_decides_nothing(cast: Cast) -> None:
    request = await cast.submit()
    message = await cast.message_to(MODERATOR)
    # The provider took the role away, and the person has signed in since.
    await cast.world.sign_in("moderator", "requester", name="Bob Moderator")

    await cast.press(MODERATOR, message, "Approve")

    assert (await cast.read(request))["status"] == "new"
    assert cast.telegram.answers == ["This action is not available to you"]
    assert message not in cast.telegram.keyboards


async def test_a_finance_director_gets_no_buttons_for_their_own_request(cast: Cast) -> None:
    both = await cast.world.sign_in("director-requester", "finance_director", "requester")
    await link_telegram(both, cast.telegram, 9)
    request = await cast.world.submit(both, cast.lists, cast.moderator)
    await cast.deliver()
    cast.telegram.sent.clear()
    cast.telegram.keyboards.clear()

    await cast.moderator.post(f"/v1/requests/{request['id']}/escalate", json={})
    await cast.deliver()

    # The other finance director decides; the author of the request is not even told that it waits.
    assert {to for to, _ in cast.telegram.sent} == {DIRECTOR}
    assert len(cast.telegram.keyboards) == 1
