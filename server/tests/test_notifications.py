"""The messages people get about requests: who is told what, when, and what stops a message."""

import datetime
import html
import re
from dataclasses import dataclass
from typing import Any

import pytest

from internal.config import settings
from internal.service.telegram import TelegramUnavailable
from tests.conftest import Clock, FakeTelegram, Session, World, link_telegram, send_waiting

day = datetime.date

AUTHOR, MODERATOR, DIRECTOR, PAYER, OTHER_PAYER, OTHER_MODERATOR = 1, 2, 3, 4, 5, 6


def plain(text: str) -> str:
    """A message as a person reads it: without the markup."""
    return html.unescape(re.sub(r"<[^>]+>", "", text))


def link(request: dict[str, Any], name: str = "Request") -> str:
    """The number of a request as a message writes it: it opens the request."""
    return f'<a href="https://zrs.test/requests/{request["id"]}">{name} No. {request["id"]}</a>'


def waits_for_decision(request: dict[str, Any]) -> str:
    return f"⚪ Request No. {request['id']} waits for your decision"


def waits_for_payment(request: dict[str, Any]) -> str:
    return f"🟢 Request No. {request['id']} is approved and waits for payment"


def is_approved(request: dict[str, Any]) -> str:
    return f"🟢 Your request No. {request['id']} is approved"


def is_returned(request: dict[str, Any]) -> str:
    return f"🟠 Request No. {request['id']} is returned to you for correction"


def is_paid(request: dict[str, Any]) -> str:
    return f"✅ Request No. {request['id']}: a payment is marked"


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
    other_payer: Session
    other_moderator: Session

    async def submit(self, **overrides: Any) -> dict[str, Any]:
        return await self.world.submit(self.author, self.lists, self.moderator, **overrides)

    async def act(self, person: Session, request: dict[str, Any], action: str, **body: Any) -> dict[str, Any]:
        response = await person.post(f"/v1/requests/{request['id']}/{action}", json=body)
        assert response.status_code == 200, response.text
        return response.json()

    async def told(self) -> list[tuple[int, str]]:
        """Send what waits and say who got what: the chat and the first line of each message."""
        await send_waiting(self.telegram, self.clock.today)
        sent = [(chat, plain(text).split("\n", 1)[0]) for chat, text in self.telegram.sent]
        self.telegram.sent.clear()
        return sorted(sent)

    async def texts(self) -> list[str]:
        await send_waiting(self.telegram, self.clock.today)
        texts = [text for _, text in self.telegram.sent]
        self.telegram.sent.clear()
        return texts


@pytest.fixture
async def cast(world: World, clock: Clock, telegram: FakeTelegram) -> Cast:
    """Everyone has linked a chat numbered after them."""
    people = {
        "author": await world.sign_in("author", "requester", name="Alice Author"),
        "moderator": await world.sign_in("moderator", "moderator", name="Bob Moderator"),
        "director": await world.sign_in("director", "finance_director", name="Carol Director"),
        "payer": await world.sign_in("payer", "payer", name="Dave Payer"),
        "other_payer": await world.sign_in("other-payer", "payer", name="Frank Payer"),
        "other_moderator": await world.sign_in("other-moderator", "moderator", name="Mia Moderator"),
    }
    lists = await world.reference_lists()
    for chat, person in zip(
        (AUTHOR, MODERATOR, DIRECTOR, PAYER, OTHER_PAYER, OTHER_MODERATOR), people.values(), strict=True
    ):
        await link_telegram(person, telegram, chat)
    return Cast(world=world, clock=clock, telegram=telegram, lists=lists, **people)


# --- a request that starts to wait for somebody ---


async def test_a_new_request_is_told_to_its_moderator(cast: Cast) -> None:
    request = await cast.submit(deadline="2026-10-20")

    assert await cast.texts() == [
        (
            f"⚪ <b>{link(request)} waits for your decision</b>\n"
            "Monthly subscription for the video tool\n"
            "<b>1,590.00\u00a0₽</b> · Normal · by 2026-10-20\n"
            "Author: Alice Author"
        )
    ]


async def test_a_request_passed_on_is_told_to_every_finance_director_but_its_author_and_moderator(
    cast: Cast,
) -> None:
    second_director = await cast.world.sign_in("second-director", "finance_director", "moderator")
    await link_telegram(second_director, cast.telegram, 9)
    # The second director moderates this request, so the request does not wait for them as a director.
    request = await cast.world.submit(cast.author, cast.lists, second_director)
    await cast.told()

    await cast.act(second_director, request, "escalate", comment="Above my limit")

    assert await cast.texts() == [
        (
            f"🟡 <b>{link(request)} is passed to you for approval</b>\n"
            "Monthly subscription for the video tool\n"
            "<b>1,590.00\u00a0₽</b> · Normal\n"
            "Author: Alice Author · Moderator: Second-Director\n"
            "<blockquote>Above my limit</blockquote>"
        )
    ]


async def test_an_approved_request_is_told_to_its_payer_alone(cast: Cast) -> None:
    request = await cast.submit(payer_id=cast.payer.id, recurrence="month", payment_form_id=None)
    await cast.told()

    await cast.act(cast.moderator, request, "approve")

    assert await cast.told() == [(AUTHOR, is_approved(request)), (PAYER, waits_for_payment(request))]


async def test_the_payer_is_told_how_and_when_to_pay(cast: Cast) -> None:
    request = await cast.submit(
        payer_id=cast.payer.id, recurrence="month", deadline="2026-10-20", payment_form_id=cast.lists["payment_form_id"]
    )
    await cast.told()

    await cast.act(cast.moderator, request, "approve")

    assert (await cast.texts())[0] == (
        f"🟢 <b>{link(request)} is approved and waits for payment</b>\n"
        "Monthly subscription for the video tool\n"
        "<b>1,590.00\u00a0₽</b> · Normal · Card · by 2026-10-20 · monthly\n"
        "Author: Alice Author"
    )


async def test_an_approved_request_without_a_payer_is_told_to_every_payer(cast: Cast) -> None:
    request = await cast.submit()
    await cast.told()

    await cast.act(cast.moderator, request, "approve")

    assert await cast.told() == [
        (AUTHOR, is_approved(request)),
        (PAYER, waits_for_payment(request)),
        (OTHER_PAYER, waits_for_payment(request)),
    ]


async def test_a_returned_request_is_told_to_its_author_with_the_reason(cast: Cast) -> None:
    request = await cast.submit()
    await cast.told()

    await cast.act(cast.moderator, request, "return", comment="Add the invoice & the <contract>")

    assert await cast.texts() == [
        (
            f"🟠 <b>{link(request)} is returned to you for correction</b>\n"
            "Monthly subscription for the video tool\n"
            "Returned by Bob Moderator\n"
            "<blockquote>Add the invoice &amp; the &lt;contract&gt;</blockquote>"
        )
    ]


async def test_a_request_given_another_moderator_is_told_to_them(cast: Cast) -> None:
    request = await cast.submit()
    await cast.told()

    await cast.author.patch(f"/v1/requests/{request['id']}", json={"moderator_id": cast.other_moderator.id})

    assert await cast.told() == [(OTHER_MODERATOR, waits_for_decision(request))]


async def test_a_change_of_the_payer_is_told_to_the_new_one(cast: Cast) -> None:
    request = await cast.submit(payer_id=cast.payer.id)
    await cast.act(cast.moderator, request, "approve")
    await cast.told()

    await cast.act(cast.director, request, "reassign", payer_id=cast.other_payer.id)

    assert await cast.told() == [(OTHER_PAYER, waits_for_payment(request))]


async def test_a_person_without_a_linked_chat_is_told_nothing(cast: Cast) -> None:
    await cast.moderator.delete("/v1/telegram-link")

    request = await cast.submit()

    assert await cast.told() == []
    queue = (await cast.moderator.get("/v1/requests", params={"awaiting_me": True})).json()
    assert [item["id"] for item in queue["items"]] == [request["id"]]


async def test_a_request_that_no_longer_waits_is_not_told(cast: Cast) -> None:
    request = await cast.submit()

    # The moderator decided before the sender came round.
    await cast.act(cast.moderator, request, "return")

    assert await cast.told() == [(AUTHOR, is_returned(request))]


async def test_a_request_paid_while_the_sender_is_at_work_is_not_told_to_the_other_payer(cast: Cast) -> None:
    request = await cast.submit()
    await cast.told()
    await cast.act(cast.moderator, request, "approve")

    class PaysMeanwhile:
        """Stands in for Telegram: the first payer pays the request while their own message goes out."""

        def __init__(self) -> None:
            self.sent: list[tuple[int, str]] = []

        async def send_message(self, chat_id: int, text: str, keyboard: object = None) -> int:
            if not self.sent:
                await cast.act(cast.payer, request, "pay", paid_on="2026-10-09", amount="100")
            self.sent.append((chat_id, plain(text).split("\n", 1)[0]))
            return len(self.sent)

    slow = PaysMeanwhile()
    await send_waiting(slow, cast.clock.today)  # type: ignore[arg-type]

    # The message to the other payer waited in the same pass, about a request that waits no more.
    assert slow.sent == [
        (PAYER, waits_for_payment(request)),
        (AUTHOR, is_approved(request)),
        (AUTHOR, is_paid(request)),
    ]


async def test_nobody_is_told_about_what_they_did_themselves(cast: Cast) -> None:
    both = await cast.world.sign_in("moderator-payer", "moderator", "payer")
    await link_telegram(both, cast.telegram, 9)
    request = await cast.world.submit(cast.author, cast.lists, both, payer_id=both.id)
    await cast.told()

    # The one who approves is the payer the request now waits for.
    await cast.act(both, request, "approve")

    assert await cast.told() == [(AUTHOR, is_approved(request))]


# --- the author is told what was decided ---


async def test_the_author_is_told_who_approved_the_request(cast: Cast) -> None:
    request = await cast.submit()
    await cast.told()

    await cast.act(cast.moderator, request, "approve", comment="Pay from the marketing budget")

    assert (await cast.texts())[-1] == (
        f"🟢 <b>Your {link(request, 'request')} is approved</b>\n"
        "Monthly subscription for the video tool\n"
        "<b>1,590.00\u00a0₽</b>\n"
        "Approved by Bob Moderator\n"
        "<blockquote>Pay from the marketing budget</blockquote>"
    )


async def test_the_author_is_told_who_rejected_the_request_and_why(cast: Cast) -> None:
    by_moderator = await cast.submit()
    by_director = await cast.submit()
    await cast.act(cast.moderator, by_director, "escalate")
    await cast.told()

    await cast.act(cast.moderator, by_moderator, "reject", comment="Not this quarter")
    await cast.act(cast.director, by_director, "reject")

    assert await cast.texts() == [
        (
            f"⚫ <b>Your {link(by_moderator, 'request')} is rejected</b>\n"
            "Monthly subscription for the video tool\n"
            "Rejected by the moderator Bob Moderator\n"
            "<blockquote>Not this quarter</blockquote>"
        ),
        (
            f"🔴 <b>Your {link(by_director, 'request')} is rejected</b>\n"
            "Monthly subscription for the video tool\n"
            "Rejected by the finance director"
        ),
    ]


async def test_an_author_who_cancels_is_told_nothing(cast: Cast) -> None:
    request = await cast.submit()
    await cast.told()

    await cast.act(cast.author, request, "cancel")

    assert await cast.told() == []


async def test_the_author_is_told_of_a_payment_with_its_date_and_amount(cast: Cast) -> None:
    request = await cast.submit()
    await cast.act(cast.moderator, request, "approve")
    await cast.told()

    await cast.act(cast.payer, request, "pay", paid_on="2026-10-09", amount="1500.50")

    assert await cast.texts() == [
        (
            f"✅ <b>{link(request)}: a payment is marked</b>\n"
            "Monthly subscription for the video tool\n"
            "<b>1,500.50\u00a0₽</b> · 2026-10-09"
        )
    ]


async def test_the_author_is_told_of_every_payment_of_a_recurring_request_and_not_of_its_finish(cast: Cast) -> None:
    request = await cast.submit(recurrence="month", payer_id=cast.payer.id)
    await cast.act(cast.moderator, request, "approve")
    await cast.told()

    await cast.act(cast.payer, request, "pay", paid_on="2026-10-09", amount="100")
    first = await cast.told()
    cast.clock.today = day(2026, 10, 10)
    await cast.act(cast.payer, request, "pay", paid_on="2026-10-10", amount="200")
    second = await cast.told()
    await cast.act(cast.director, request, "finish")
    finished = await cast.told()

    assert (first, second, finished) == ([(AUTHOR, is_paid(request))], [(AUTHOR, is_paid(request))], [])


# --- comments ---


async def test_a_comment_of_the_payer_is_told_to_the_author_and_the_moderator(cast: Cast) -> None:
    request = await cast.submit()
    await cast.act(cast.moderator, request, "approve")
    await cast.told()

    await cast.payer.post(f"/v1/requests/{request['id']}/comments", json={"comment": "Which account do I pay from?"})

    assert (
        await cast.texts()
        == [
            (
                f"💬 <b>Dave Payer about {link(request, 'request')}</b>\n"
                "Monthly subscription for the video tool\n"
                "<blockquote>Which account do I pay from?</blockquote>"
            )
        ]
        * 2
    )


async def test_a_comment_of_the_author_is_told_to_the_moderator_alone(cast: Cast) -> None:
    request = await cast.submit()
    await cast.told()

    await cast.author.post(f"/v1/requests/{request['id']}/comments", json={"comment": "The invoice is attached"})

    assert await cast.told() == [(MODERATOR, f"💬 Alice Author about request No. {request['id']}")]


async def test_a_long_situation_and_a_long_comment_are_cut_short(cast: Cast) -> None:
    request = await cast.submit(situation="S" * 500 + "\nthe second line")
    await cast.told()

    await cast.author.post(f"/v1/requests/{request['id']}/comments", json={"comment": "C" * 5000})

    _headline, gist, comment = plain((await cast.texts())[0]).split("\n")
    assert (len(gist), gist[-1]) == (200, "…")
    assert (len(comment), comment[-1]) == (700, "…")


# --- a request that comes back with a new period ---


async def test_a_new_period_is_told_to_the_payer_once(cast: Cast) -> None:
    request = await cast.submit(recurrence="month", payer_id=cast.payer.id)
    await cast.act(cast.moderator, request, "approve")
    await cast.act(cast.payer, request, "pay", paid_on="2026-10-09", amount="100")
    await cast.told()
    due = (PAYER, f"🟢 Request No. {request['id']}: a payment for the new period is due")

    cast.clock.today = day(2026, 10, 31)
    before = await cast.told()
    cast.clock.today = day(2026, 11, 1)
    on_the_first = await cast.told()
    again = await cast.told()
    cast.clock.today = day(2026, 11, 20)
    later = await cast.told()
    cast.clock.today = day(2026, 12, 1)
    next_period = await cast.told()

    assert (before, on_the_first, again, later, next_period) == ([], [due], [], [], [due])


# --- Telegram failing ---


async def test_an_action_goes_through_while_telegram_is_down_and_the_messages_follow(cast: Cast) -> None:
    request = await cast.submit(payer_id=cast.payer.id)
    await cast.told()
    cast.telegram.available = False

    approved = await cast.act(cast.moderator, request, "approve")
    with pytest.raises(TelegramUnavailable):
        await cast.told()
    cast.telegram.available = True

    assert approved["status"] == "approved"
    assert await cast.told() == [(AUTHOR, is_approved(request)), (PAYER, waits_for_payment(request))]


async def test_a_sent_message_is_not_sent_again(cast: Cast) -> None:
    await cast.submit()

    first = await cast.told()
    second = await cast.told()

    assert len(first) == 1
    assert second == []


async def test_a_blocked_bot_takes_the_link_off_and_the_rest_is_sent(cast: Cast) -> None:
    request = await cast.submit()
    await cast.told()
    cast.telegram.closed.add(PAYER)

    await cast.act(cast.moderator, request, "approve")

    assert await cast.told() == [(AUTHOR, is_approved(request)), (OTHER_PAYER, waits_for_payment(request))]
    assert (await cast.payer.get("/v1/me")).json()["notifications"]["telegram_linked"] is False


# --- the installation ---


async def test_the_messages_are_written_in_the_language_of_the_installation(
    cast: Cast, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "UI_LOCALE", "ru")
    request = await cast.submit(deadline="2026-10-20", amount="1234567.5")

    assert await cast.texts() == [
        (
            f'⚪ <b><a href="https://zrs.test/requests/{request["id"]}">Запрос № {request["id"]}</a> '
            "ждёт вашего решения</b>\n"
            "Monthly subscription for the video tool\n"
            "<b>1\u00a0234\u00a0567,50\u00a0₽</b> · Normal · до 20.10.2026\n"
            "Автор: Alice Author"
        )
    ]


async def test_an_installation_without_notifications_writes_no_messages(
    cast: Cast, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "NOTIFICATIONS", "off")
    request = await cast.submit()
    await cast.act(cast.moderator, request, "approve")
    monkeypatch.setattr(settings, "NOTIFICATIONS", "telegram")

    assert await cast.told() == []
