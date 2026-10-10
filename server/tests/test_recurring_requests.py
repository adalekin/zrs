"""A request paid every period: its recurrence, its payments, how it is closed and whose queue it stands in."""

import datetime
import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.conftest import Clock, Session, World

MIGRATION = Path(__file__).parent.parent / "migrations" / "versions" / "0006_recurrence_and_payments.py"

day = datetime.date


@dataclass
class Cast:
    world: World
    clock: Clock
    lists: dict[str, int]
    author: Session
    moderator: Session
    director: Session
    payer: Session
    other_payer: Session

    async def submit(self, **overrides: Any) -> dict[str, Any]:
        return await self.world.submit(self.author, self.lists, self.moderator, **overrides)

    async def approved(self, **overrides: Any) -> dict[str, Any]:
        """A request approved by its moderator."""
        request = await self.submit(**overrides)
        response = await self.moderator.post(f"/v1/requests/{request['id']}/approve", json={})
        assert response.status_code == 200, response.text
        return response.json()

    async def pay(self, request: dict[str, Any], on: datetime.date, amount: str = "1590.00", by: Session | None = None):
        return await (by or self.payer).post(
            f"/v1/requests/{request['id']}/pay", json={"paid_on": on.isoformat(), "amount": amount}
        )

    async def read(self, request: dict[str, Any]) -> dict[str, Any]:
        return (await self.director.get(f"/v1/requests/{request['id']}")).json()

    async def queue(self, person: Session) -> list[int]:
        response = await person.get("/v1/requests", params={"awaiting_me": True, "size": 100})
        return sorted(item["id"] for item in response.json()["items"])


@pytest.fixture
async def cast(world: World, clock: Clock) -> Cast:
    return Cast(
        world=world,
        clock=clock,
        lists=await world.reference_lists(),
        author=await world.sign_in("author", "requester"),
        moderator=await world.sign_in("moderator", "moderator"),
        director=await world.sign_in("director", "finance_director"),
        payer=await world.sign_in("payer", "payer"),
        other_payer=await world.sign_in("other-payer", "payer"),
    )


def field(response: Any) -> str:
    """The field a refusal names."""
    return response.json()["detail"][0]["loc"][-1]


# --- the recurrence of a request ---


@pytest.mark.parametrize("recurrence", ["week", "month", "quarter", "year"])
async def test_a_request_is_submitted_with_a_recurrence(cast: Cast, recurrence: str) -> None:
    request = await cast.submit(recurrence=recurrence)

    assert request["recurrence"] == recurrence
    assert (await cast.read(request))["recurrence"] == recurrence


async def test_a_request_without_a_recurrence_is_paid_once(cast: Cast) -> None:
    request = await cast.submit()

    assert request["recurrence"] is None


async def test_an_unknown_recurrence_names_the_field(cast: Cast) -> None:
    body = cast.world.request_body(cast.lists, cast.moderator, recurrence="fortnight")

    response = await cast.author.post("/v1/requests", json=body)

    assert response.status_code == 422
    assert field(response) == "recurrence"


async def test_the_author_changes_and_takes_off_the_recurrence_of_a_new_request(cast: Cast) -> None:
    request = await cast.submit(recurrence="month")
    url = f"/v1/requests/{request['id']}"

    changed = await cast.author.patch(url, json={"recurrence": "quarter"})
    cleared = await cast.author.patch(url, json={"recurrence": None})

    assert changed.json()["recurrence"] == "quarter"
    assert cleared.json()["recurrence"] is None


async def test_the_recurrence_of_an_approved_request_is_not_changed(cast: Cast) -> None:
    request = await cast.approved(recurrence="month")

    response = await cast.author.patch(f"/v1/requests/{request['id']}", json={"recurrence": "year"})

    assert response.status_code == 409
    assert (await cast.read(request))["recurrence"] == "month"


async def test_a_request_is_submitted_without_the_words_about_its_period(cast: Cast) -> None:
    body = cast.world.request_body(cast.lists, cast.moderator, recurrence="month")
    del body["payment_period"]

    response = await cast.author.post("/v1/requests", json=body)

    assert response.status_code == 201, response.text
    assert response.json()["payment_period"] is None
    assert response.json()["recurrence"] == "month"


async def test_the_author_takes_off_the_words_about_the_period(cast: Cast) -> None:
    request = await cast.submit(payment_period="by the fifth of the month")

    response = await cast.author.patch(f"/v1/requests/{request['id']}", json={"payment_period": None})

    assert request["payment_period"] == "by the fifth of the month"
    assert response.json()["payment_period"] is None


# --- marking a payment ---


async def test_paying_a_request_paid_once_closes_it_with_one_payment(cast: Cast) -> None:
    request = await cast.approved()

    response = await cast.pay(request, day(2026, 10, 9), "1500.50")

    paid = response.json()
    assert paid["status"] == "paid"
    assert paid["payer"]["id"] == cast.payer.id
    assert paid["paid_on"] == "2026-10-09"
    assert [(p["paid_on"], p["amount"], p["person"]["id"]) for p in paid["payments"]] == [
        ("2026-10-09", "1500.5000", cast.payer.id)
    ]


async def test_paying_without_an_amount_names_the_field(cast: Cast) -> None:
    request = await cast.approved()

    response = await cast.payer.post(f"/v1/requests/{request['id']}/pay", json={"paid_on": "2026-10-09"})

    assert response.status_code == 422
    assert field(response) == "amount"
    assert (await cast.read(request))["status"] == "approved"


@pytest.mark.parametrize("amount", ["0", "-10"])
async def test_paying_an_amount_that_is_not_positive_names_the_field(cast: Cast, amount: str) -> None:
    request = await cast.approved()

    response = await cast.pay(request, day(2026, 10, 9), amount)

    assert response.status_code == 422
    assert field(response) == "amount"
    assert (await cast.read(request))["payments"] == []


async def test_an_amount_given_to_another_action_names_the_field(cast: Cast) -> None:
    request = await cast.submit()

    response = await cast.moderator.post(f"/v1/requests/{request['id']}/approve", json={"amount": "10"})

    assert response.status_code == 422
    assert field(response) == "amount"


async def test_paying_a_recurring_request_leaves_it_approved(cast: Cast) -> None:
    request = await cast.approved(recurrence="month")

    response = await cast.pay(request, day(2026, 10, 9), "1700.00")

    paid = response.json()
    assert paid["status"] == "approved"
    assert paid["paid_on"] == "2026-10-09"
    assert [(p["paid_on"], p["amount"]) for p in paid["payments"]] == [("2026-10-09", "1700.0000")]
    # A payment is no decision: the journal keeps the submission and the approval alone.
    assert [entry["status"] for entry in paid["journal"]] == ["new", "approved"]


async def test_a_recurring_request_takes_the_next_payment(cast: Cast) -> None:
    request = await cast.approved(recurrence="month")
    await cast.pay(request, day(2026, 10, 9))
    cast.clock.today = day(2026, 11, 3)

    response = await cast.pay(request, day(2026, 11, 3), "1650.00")

    assert response.json()["status"] == "approved"
    assert len(response.json()["payments"]) == 2


async def test_the_payments_of_a_request_read_from_the_latest(cast: Cast) -> None:
    request = await cast.approved(recurrence="month")
    cast.clock.today = day(2026, 12, 2)
    await cast.pay(request, day(2026, 10, 9), "100")
    await cast.pay(request, day(2026, 12, 2), "300", by=cast.other_payer)
    # Marked last, paid in between.
    await cast.pay(request, day(2026, 11, 3), "200")

    read = await cast.read(request)

    assert [(p["paid_on"], p["amount"], p["person"]["id"]) for p in read["payments"]] == [
        ("2026-12-02", "300.0000", cast.other_payer.id),
        ("2026-11-03", "200.0000", cast.payer.id),
        ("2026-10-09", "100.0000", cast.payer.id),
    ]
    assert read["paid_on"] == "2026-12-02"


async def test_paying_a_recurring_request_without_a_payer_leaves_it_to_every_payer(cast: Cast) -> None:
    request = await cast.approved(recurrence="month")

    paid = (await cast.pay(request, day(2026, 10, 9))).json()
    cast.clock.today = day(2026, 11, 1)

    assert paid["payer"] is None
    assert request["id"] in await cast.queue(cast.payer)
    assert request["id"] in await cast.queue(cast.other_payer)


async def test_paying_a_recurring_request_keeps_the_payer_it_was_assigned(cast: Cast) -> None:
    request = await cast.approved(recurrence="month", payer_id=cast.payer.id)

    paid = (await cast.pay(request, day(2026, 10, 9))).json()

    assert paid["payer"]["id"] == cast.payer.id
    assert (await cast.pay(request, day(2026, 10, 10), by=cast.other_payer)).status_code == 403


# --- closing a recurring request ---


async def test_the_author_finishes_a_recurring_request_that_was_paid(cast: Cast) -> None:
    request = await cast.approved(recurrence="month")
    await cast.pay(request, day(2026, 10, 9))

    response = await cast.author.post(f"/v1/requests/{request['id']}/finish", json={})

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "paid"
    assert response.json()["journal"][-1]["status"] == "paid"
    assert response.json()["journal"][-1]["person"]["id"] == cast.author.id
    assert (await cast.pay(request, day(2026, 11, 3))).status_code == 409


async def test_the_finance_director_finishes_a_recurring_request_that_was_paid(cast: Cast) -> None:
    request = await cast.approved(recurrence="month")
    await cast.pay(request, day(2026, 10, 9))

    response = await cast.director.post(f"/v1/requests/{request['id']}/finish", json={})

    assert response.json()["status"] == "paid"
    assert len(response.json()["payments"]) == 1


async def test_a_recurring_request_without_a_payment_is_not_finished(cast: Cast) -> None:
    request = await cast.approved(recurrence="month")

    response = await cast.author.post(f"/v1/requests/{request['id']}/finish", json={})

    assert response.status_code == 409
    assert (await cast.read(request))["status"] == "approved"


async def test_a_request_paid_once_is_not_finished(cast: Cast) -> None:
    request = await cast.approved()

    response = await cast.author.post(f"/v1/requests/{request['id']}/finish", json={})

    assert response.status_code == 409
    assert (await cast.read(request))["status"] == "approved"


async def test_a_payer_does_not_finish_a_request(cast: Cast) -> None:
    request = await cast.approved(recurrence="month")
    await cast.pay(request, day(2026, 10, 9))

    response = await cast.payer.post(f"/v1/requests/{request['id']}/finish", json={})

    assert response.status_code == 403
    assert (await cast.read(request))["status"] == "approved"


async def test_the_author_cancels_a_recurring_request_before_its_first_payment_only(cast: Cast) -> None:
    unpaid = await cast.approved(recurrence="month")
    paid = await cast.approved(recurrence="month")
    await cast.pay(paid, day(2026, 10, 9))

    cancelled = await cast.author.post(f"/v1/requests/{unpaid['id']}/cancel", json={})
    refused = await cast.author.post(f"/v1/requests/{paid['id']}/cancel", json={})

    assert cancelled.json()["status"] == "rejected"
    assert refused.status_code == 409
    assert (await cast.read(paid))["status"] == "approved"


async def test_finishing_is_offered_only_where_it_can_be_done(cast: Cast) -> None:
    once = await cast.approved()
    unpaid = await cast.approved(recurrence="month")
    paid = await cast.approved(recurrence="month")
    await cast.pay(paid, day(2026, 10, 9))

    async def actions(person: Session, request: dict[str, Any]) -> list[str]:
        return (await person.get(f"/v1/requests/{request['id']}")).json()["actions"]

    assert "finish" in await actions(cast.author, paid)
    assert "finish" in await actions(cast.director, paid)
    assert "finish" not in await actions(cast.payer, paid)
    assert "finish" not in await actions(cast.author, unpaid)
    assert "finish" not in await actions(cast.author, once)
    assert "cancel" in await actions(cast.author, unpaid)
    assert "cancel" not in await actions(cast.author, paid)
    # Paying again in the same period stays possible: the payments say what was paid.
    assert "pay" in await actions(cast.payer, paid)


# --- the queue of a payer ---


async def test_a_recurring_request_without_a_payment_waits_for_its_payer(cast: Cast) -> None:
    request = await cast.approved(recurrence="month")

    assert request["id"] in await cast.queue(cast.payer)
    assert (await cast.read(request))["next_payment_from"] is None


async def test_a_monthly_request_leaves_the_queue_till_the_next_month(cast: Cast) -> None:
    request = await cast.approved(recurrence="month")
    cast.clock.today = day(2026, 10, 12)
    await cast.pay(request, day(2026, 10, 12))

    cast.clock.today = day(2026, 10, 20)
    out = await cast.queue(cast.payer), (await cast.read(request))["next_payment_from"]
    cast.clock.today = day(2026, 10, 31)
    still_out = await cast.queue(cast.payer)
    cast.clock.today = day(2026, 11, 1)
    back = await cast.queue(cast.payer), (await cast.read(request))["next_payment_from"]

    assert out == ([], "2026-11-01")
    assert still_out == []
    assert back == ([request["id"]], None)


async def test_a_weekly_request_comes_back_on_monday(cast: Cast) -> None:
    request = await cast.approved(recurrence="week")
    # A Tuesday.
    await cast.pay(request, day(2026, 10, 6))

    cast.clock.today = day(2026, 10, 9)
    friday = await cast.queue(cast.payer), (await cast.read(request))["next_payment_from"]
    cast.clock.today = day(2026, 10, 11)
    sunday = await cast.queue(cast.payer)
    cast.clock.today = day(2026, 10, 12)
    monday = await cast.queue(cast.payer)

    assert friday == ([], "2026-10-12")
    assert sunday == []
    assert monday == [request["id"]]


async def test_a_quarterly_request_stays_out_of_the_queue_till_the_next_quarter(cast: Cast) -> None:
    request = await cast.approved(recurrence="quarter")
    cast.clock.today = day(2026, 10, 12)
    await cast.pay(request, day(2026, 10, 12))

    cast.clock.today = day(2026, 11, 1)
    november = await cast.queue(cast.payer), (await cast.read(request))["next_payment_from"]
    cast.clock.today = day(2026, 12, 31)
    december = await cast.queue(cast.payer)
    cast.clock.today = day(2027, 1, 1)
    january = await cast.queue(cast.payer)

    assert november == ([], "2027-01-01")
    assert december == []
    assert january == [request["id"]]


async def test_the_list_says_when_the_next_payment_is_due(cast: Cast) -> None:
    request = await cast.approved(recurrence="month")
    await cast.pay(request, day(2026, 10, 9))

    page = (await cast.director.get("/v1/requests", params={"size": 100})).json()

    assert [(item["recurrence"], item["next_payment_from"]) for item in page["items"]] == [("month", "2026-11-01")]


async def test_a_request_is_in_the_queue_exactly_while_it_names_no_day_of_the_next_payment(cast: Cast) -> None:
    requests = [await cast.approved(recurrence=recurrence) for recurrence in ("week", "month", "quarter", "year")]
    for request in requests:
        await cast.pay(request, day(2026, 10, 6))

    for offset in range(0, 460, 5):
        cast.clock.today = day(2026, 10, 6) + datetime.timedelta(days=offset)
        queue = await cast.queue(cast.payer)
        for request in requests:
            waits = (await cast.read(request))["next_payment_from"] is None
            assert (request["id"] in queue) is waits, (request["recurrence"], cast.clock.today)


async def test_the_totals_of_the_queue_count_what_the_queue_lists(cast: Cast) -> None:
    paid = await cast.approved(recurrence="month")
    await cast.approved(recurrence="month")
    await cast.pay(paid, day(2026, 10, 9))

    async def approved_waiting() -> int:
        totals = (await cast.payer.get("/v1/request-totals", params={"awaiting_me": True})).json()
        return next(entry["count"] for entry in totals if entry["status"] == "approved")

    cast.clock.today = day(2026, 10, 20)
    this_month = await approved_waiting()
    cast.clock.today = day(2026, 11, 1)
    next_month = await approved_waiting()

    assert (this_month, next_month) == (1, 2)


# --- the requests paid before payments were recorded ---


async def test_the_migration_gives_a_paid_request_one_payment_of_its_own_amount(
    cast: Cast, engine: AsyncEngine
) -> None:
    request = await cast.approved(amount="2400.00")
    untouched = await cast.approved()
    await cast.pay(request, day(2026, 10, 9), "9999.00")
    spec = importlib.util.spec_from_file_location("migration_0006", MIGRATION)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    async with engine.begin() as connection:
        await connection.execute(text("DELETE FROM payment"))
        await connection.execute(text(migration.FILL_PAYMENTS))

    assert [(p["paid_on"], p["amount"], p["person"]["id"]) for p in (await cast.read(request))["payments"]] == [
        ("2026-10-09", "2400.0000", cast.payer.id)
    ]
    assert (await cast.read(untouched))["payments"] == []
