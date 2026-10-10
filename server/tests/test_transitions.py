"""The life cycle checked against the specification, independently of the table in the code."""

import datetime
from dataclasses import dataclass
from typing import Any

import pytest

from tests.conftest import SUBMITTED_ON, TODAY, Session, World

STATUSES = ["new", "returned", "escalated", "approved", "paid", "rejected"]
ACTIONS = ["approve", "escalate", "return", "reject", "resubmit", "cancel", "pay", "reassign", "finish"]
PERSONAS = ["author", "moderator", "finance_director", "payer"]

#: (persona, action, status the request is in) -> status it moves to. Everything else is refused.
ALLOWED: dict[tuple[str, str, str], str] = {
    ("author", "resubmit", "returned"): "new",
    ("author", "cancel", "new"): "rejected",
    ("author", "cancel", "returned"): "rejected",
    ("author", "cancel", "escalated"): "rejected",
    ("author", "cancel", "approved"): "rejected",
    ("moderator", "approve", "new"): "approved",
    ("moderator", "escalate", "new"): "escalated",
    ("moderator", "return", "new"): "returned",
    ("moderator", "reject", "new"): "rejected",
    ("finance_director", "approve", "escalated"): "approved",
    ("finance_director", "return", "escalated"): "returned",
    ("finance_director", "reject", "escalated"): "rejected",
    ("payer", "pay", "approved"): "paid",
    ("finance_director", "reassign", "approved"): "approved",
}
#: Given to the persona only for a recurring request, which the request of this matrix is not:
#: refused as a conflict in every status. Recurring requests have tests of their own.
FOR_RECURRING_ONLY = {("author", "finish"), ("finance_director", "finish")}
#: Actions that keep the status: their journal entry says the status did not change.
KEEP_STATUS = {"reassign"}


@dataclass
class Cast:
    author: Session
    moderator: Session
    finance_director: Session
    payer: Session
    request_id: int

    def session(self, persona: str) -> Session:
        return {
            "author": self.author,
            "moderator": self.moderator,
            "finance_director": self.finance_director,
            "payer": self.payer,
        }[persona]

    async def status(self) -> str:
        return (await self.finance_director.get(f"/v1/requests/{self.request_id}")).json()["status"]

    async def journal(self) -> list[dict[str, Any]]:
        return (await self.finance_director.get(f"/v1/requests/{self.request_id}")).json()["journal"]


async def drive(cast: Cast, status: str) -> None:
    """Bring a new request to the given status through the public actions."""
    url = f"/v1/requests/{cast.request_id}"
    steps: dict[str, list[tuple[Session, str, dict[str, Any]]]] = {
        "new": [],
        "returned": [(cast.moderator, "return", {})],
        "escalated": [(cast.moderator, "escalate", {})],
        "approved": [(cast.moderator, "approve", {})],
        "paid": [(cast.moderator, "approve", {}), (cast.payer, "pay", {"paid_on": "2026-10-01", "amount": "1590.00"})],
        "rejected": [(cast.moderator, "reject", {})],
    }
    for session, action, body in steps[status]:
        response = await session.post(f"{url}/{action}", json=body)
        assert response.status_code == 200, response.text
    assert await cast.status() == status


@pytest.fixture
async def cast(world: World) -> Cast:
    lists = await world.reference_lists()
    author = await world.sign_in("author", "requester")
    moderator = await world.sign_in("moderator", "moderator")
    finance_director = await world.sign_in("director", "finance_director")
    payer = await world.sign_in("payer", "payer")
    request = await world.submit(author, lists, moderator)
    return Cast(author, moderator, finance_director, payer, request["id"])


def never_available(persona: str, action: str) -> bool:
    if (persona, action) in FOR_RECURRING_ONLY:
        return False
    return not any(key[0] == persona and key[1] == action for key in ALLOWED)


@pytest.mark.parametrize("status", STATUSES)
@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("persona", PERSONAS)
async def test_every_combination_of_person_action_and_status(
    cast: Cast, persona: str, action: str, status: str
) -> None:
    await drive(cast, status)
    journal_before = await cast.journal()
    body = {"pay": {"paid_on": "2026-10-02", "amount": "1590.00"}, "reassign": {"payer_id": cast.payer.id}}.get(
        action, {}
    )

    response = await cast.session(persona).post(f"/v1/requests/{cast.request_id}/{action}", json=body)

    target = ALLOWED.get((persona, action, status))
    if target is not None:
        assert response.status_code == 200, response.text
        assert response.json()["status"] == target
        assert await cast.status() == target
        journal = await cast.journal()
        assert len(journal) == len(journal_before) + 1
        assert journal[-1]["status"] == target
        assert journal[-1]["status_changed"] is (action not in KEEP_STATUS)
        assert journal[-1]["person"]["id"] == cast.session(persona).id
        return

    if never_available(persona, action):
        assert response.status_code == 403, response.text
    else:
        assert response.status_code == 409, response.text
        assert response.json()["status"] == status
    assert await cast.status() == status
    assert await cast.journal() == journal_before


async def test_an_unknown_action_is_refused_as_invalid(cast: Cast) -> None:
    response = await cast.moderator.post(f"/v1/requests/{cast.request_id}/destroy")

    assert response.status_code == 422


# --- the second level ---


async def test_a_finance_director_cannot_approve_their_own_request(world: World) -> None:
    lists = await world.reference_lists()
    author = await world.sign_in("author-director", "requester", "finance_director")
    moderator = await world.sign_in("moderator", "moderator")
    request = await world.submit(author, lists, moderator)
    await moderator.post(f"/v1/requests/{request['id']}/escalate")

    response = await author.post(f"/v1/requests/{request['id']}/approve")

    assert response.status_code == 403
    body = (await author.get(f"/v1/requests/{request['id']}")).json()
    assert body["status"] == "escalated"
    assert body["actions"] == ["cancel"]


async def test_a_moderator_cannot_approve_as_finance_director_what_they_escalated(world: World) -> None:
    lists = await world.reference_lists()
    author = await world.sign_in("author", "requester")
    moderator = await world.sign_in("moderator-director", "moderator", "finance_director")
    other_director = await world.sign_in("other-director", "finance_director")
    request = await world.submit(author, lists, moderator)
    await moderator.post(f"/v1/requests/{request['id']}/escalate")

    response = await moderator.post(f"/v1/requests/{request['id']}/approve")

    assert response.status_code == 409
    assert response.json()["status"] == "escalated"
    assert (await moderator.get(f"/v1/requests/{request['id']}")).json()["actions"] == []
    assert (await other_director.post(f"/v1/requests/{request['id']}/approve")).json()["status"] == "approved"


async def test_a_moderator_who_lost_the_role_can_no_longer_decide(world: World) -> None:
    lists = await world.reference_lists()
    author = await world.sign_in("author", "requester")
    moderator = await world.sign_in("moderator", "moderator")
    request = await world.submit(author, lists, moderator)

    demoted = await world.sign_in("moderator", "requester")

    assert (await demoted.post(f"/v1/requests/{request['id']}/approve")).status_code == 404


# --- resubmitting, cancelling, paying ---


async def test_a_request_returned_by_the_finance_director_goes_back_to_its_moderator(cast: Cast) -> None:
    await drive(cast, "escalated")
    await cast.finance_director.post(f"/v1/requests/{cast.request_id}/return", json={"comment": "No invoice"})

    response = await cast.author.post(f"/v1/requests/{cast.request_id}/resubmit")

    assert response.json()["status"] == "new"
    assert response.json()["moderator"]["id"] == cast.moderator.id
    waiting = (await cast.moderator.get("/v1/requests", params={"awaiting_me": True})).json()
    assert [item["id"] for item in waiting["items"]] == [cast.request_id]


async def test_paying_records_the_payer_and_the_payment_date(cast: Cast) -> None:
    await drive(cast, "approved")

    response = await cast.payer.post(
        f"/v1/requests/{cast.request_id}/pay", json={"paid_on": "2026-10-03", "amount": "1590.00"}
    )

    body = response.json()
    assert body["status"] == "paid"
    assert body["payer"]["id"] == cast.payer.id
    assert body["paid_on"] == "2026-10-03"


async def test_paying_without_a_date_names_the_field(cast: Cast) -> None:
    await drive(cast, "approved")

    response = await cast.payer.post(f"/v1/requests/{cast.request_id}/pay", json={})

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == "paid_on"
    assert await cast.status() == "approved"


@pytest.mark.parametrize("paid_on", [SUBMITTED_ON, TODAY])
async def test_a_payment_is_dated_from_the_day_the_request_was_submitted_to_today(
    cast: Cast, paid_on: datetime.date
) -> None:
    await drive(cast, "approved")

    response = await cast.payer.post(
        f"/v1/requests/{cast.request_id}/pay", json={"paid_on": paid_on.isoformat(), "amount": "1590.00"}
    )

    assert response.status_code == 200, response.text
    assert response.json()["paid_on"] == paid_on.isoformat()


# A year typed with two digits is a date before the request, too.
@pytest.mark.parametrize("paid_on", ["0026-10-08", (SUBMITTED_ON - datetime.timedelta(days=1)).isoformat()])
async def test_a_payment_dated_before_the_request_was_submitted_is_refused(cast: Cast, paid_on: str) -> None:
    await drive(cast, "approved")

    response = await cast.payer.post(
        f"/v1/requests/{cast.request_id}/pay", json={"paid_on": paid_on, "amount": "1590.00"}
    )

    assert response.status_code == 422
    detail = response.json()["detail"][0]
    assert (detail["loc"][-1], detail["type"]) == ("paid_on", "payment_before_request")
    assert await cast.status() == "approved"


async def test_a_payment_dated_after_today_is_refused(cast: Cast) -> None:
    await drive(cast, "approved")

    response = await cast.payer.post(
        f"/v1/requests/{cast.request_id}/pay",
        json={"paid_on": (TODAY + datetime.timedelta(days=1)).isoformat(), "amount": "1590.00"},
    )

    assert response.status_code == 422
    detail = response.json()["detail"][0]
    assert (detail["loc"][-1], detail["type"]) == ("paid_on", "payment_after_today")
    assert await cast.status() == "approved"


async def test_a_paid_request_cannot_be_edited(cast: Cast) -> None:
    await drive(cast, "paid")

    response = await cast.author.patch(f"/v1/requests/{cast.request_id}", json={"amount": "1"})

    assert response.status_code == 409
    assert response.json()["status"] == "paid"


# --- the actions the API reports ---


@pytest.mark.parametrize("status", STATUSES)
@pytest.mark.parametrize("persona", PERSONAS)
async def test_the_reported_actions_match_the_specification(cast: Cast, persona: str, status: str) -> None:
    await drive(cast, status)

    body = (await cast.session(persona).get(f"/v1/requests/{cast.request_id}")).json()

    expected = sorted(action for (who, action, source) in ALLOWED if who == persona and source == status)
    assert sorted(body["actions"]) == expected
    assert body["can_edit"] is (persona == "author" and status in {"new", "returned"})
