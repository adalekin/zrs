"""The payer of a request: who may be named, who names them, whose queue the request stands in and who may pay."""

from dataclasses import dataclass
from typing import Any

import pytest

from tests.conftest import Session, World


@dataclass
class Cast:
    world: World
    lists: dict[str, int]
    author: Session
    moderator: Session
    director: Session
    payer: Session
    other_payer: Session

    async def submit(self, **overrides: Any) -> dict[str, Any]:
        return await self.world.submit(self.author, self.lists, self.moderator, **overrides)

    async def approved(self, **body: Any) -> dict[str, Any]:
        """A request approved by its moderator; ``body`` goes to the approval."""
        request = await self.submit()
        response = await self.moderator.post(f"/v1/requests/{request['id']}/approve", json=body)
        assert response.status_code == 200, response.text
        return response.json()

    async def read(self, request: dict[str, Any]) -> dict[str, Any]:
        return (await self.director.get(f"/v1/requests/{request['id']}")).json()


@pytest.fixture
async def cast(world: World) -> Cast:
    return Cast(
        world=world,
        lists=await world.reference_lists(),
        author=await world.sign_in("author", "requester"),
        moderator=await world.sign_in("moderator", "moderator"),
        director=await world.sign_in("director", "finance_director"),
        payer=await world.sign_in("payer", "payer"),
        other_payer=await world.sign_in("other-payer", "payer"),
    )


def field(response: Any) -> tuple[str, str]:
    """The field a refusal names and the rule it failed."""
    detail = response.json()["detail"][0]
    return detail["loc"][-1], detail["type"]


async def queue(person: Session) -> list[int]:
    response = await person.get("/v1/requests", params={"awaiting_me": True, "size": 100})
    return sorted(item["id"] for item in response.json()["items"])


# --- the author names the payer ---


async def test_a_request_is_submitted_with_a_payer(cast: Cast) -> None:
    request = await cast.submit(payer_id=cast.payer.id)

    assert request["status"] == "new"
    assert request["payer"]["id"] == cast.payer.id


async def test_a_request_is_submitted_without_a_payer(cast: Cast) -> None:
    request = await cast.submit()

    assert request["payer"] is None


async def test_a_person_without_the_payer_role_cannot_be_named(cast: Cast) -> None:
    body = cast.world.request_body(cast.lists, cast.moderator, payer_id=cast.moderator.id)

    response = await cast.author.post("/v1/requests", json=body)

    assert response.status_code == 422
    assert field(response) == ("payer_id", "not_a_payer")


async def test_a_person_who_never_signed_in_cannot_be_named(cast: Cast) -> None:
    body = cast.world.request_body(cast.lists, cast.moderator, payer_id=10**9)

    response = await cast.author.post("/v1/requests", json=body)

    assert response.status_code == 422
    assert field(response) == ("payer_id", "not_a_payer")


async def test_the_author_changes_and_clears_the_payer_of_a_new_request(cast: Cast) -> None:
    request = await cast.submit(payer_id=cast.payer.id)
    url = f"/v1/requests/{request['id']}"

    changed = await cast.author.patch(url, json={"payer_id": cast.other_payer.id})
    cleared = await cast.author.patch(url, json={"payer_id": None})

    assert changed.json()["payer"]["id"] == cast.other_payer.id
    assert cleared.status_code == 200
    assert cleared.json()["payer"] is None


async def test_an_author_who_is_a_payer_may_name_themselves(cast: Cast) -> None:
    author = await cast.world.sign_in("author-payer", "requester", "payer")

    request = await cast.world.submit(author, cast.lists, cast.moderator, payer_id=author.id)

    assert request["payer"]["id"] == author.id


# --- the approver names the payer ---


async def test_the_moderator_names_the_payer_when_approving(cast: Cast) -> None:
    request = await cast.approved(payer_id=cast.payer.id)

    assert request["status"] == "approved"
    assert request["payer"]["id"] == cast.payer.id


async def test_the_finance_director_replaces_the_payer_when_approving(cast: Cast) -> None:
    request = await cast.submit(payer_id=cast.payer.id)
    await cast.moderator.post(f"/v1/requests/{request['id']}/escalate")

    response = await cast.director.post(f"/v1/requests/{request['id']}/approve", json={"payer_id": cast.other_payer.id})

    assert response.json()["status"] == "approved"
    assert response.json()["payer"]["id"] == cast.other_payer.id


async def test_an_approval_that_names_nobody_keeps_the_payer(cast: Cast) -> None:
    request = await cast.submit(payer_id=cast.payer.id)

    response = await cast.moderator.post(f"/v1/requests/{request['id']}/approve")

    assert response.json()["status"] == "approved"
    assert response.json()["payer"]["id"] == cast.payer.id


async def test_an_approval_that_names_a_person_without_the_role_is_refused(cast: Cast) -> None:
    request = await cast.submit(payer_id=cast.payer.id)

    response = await cast.moderator.post(f"/v1/requests/{request['id']}/approve", json={"payer_id": cast.author.id})

    assert response.status_code == 422
    assert field(response) == ("payer_id", "not_a_payer")
    after = await cast.read(request)
    assert after["status"] == "new"
    assert after["payer"]["id"] == cast.payer.id


async def test_a_payer_cannot_be_named_by_another_action(cast: Cast) -> None:
    request = await cast.submit()

    response = await cast.moderator.post(f"/v1/requests/{request['id']}/return", json={"payer_id": cast.payer.id})

    assert response.status_code == 422
    assert field(response) == ("payer_id", "not_accepted")
    assert (await cast.read(request))["status"] == "new"


async def test_a_payment_date_cannot_be_given_to_another_action(cast: Cast) -> None:
    request = await cast.submit()

    response = await cast.moderator.post(f"/v1/requests/{request['id']}/approve", json={"paid_on": "2026-10-09"})

    assert response.status_code == 422
    assert field(response) == ("paid_on", "not_accepted")
    assert (await cast.read(request))["status"] == "new"


# --- who may pay ---


async def test_the_assigned_payer_marks_the_payment(cast: Cast) -> None:
    request = await cast.approved(payer_id=cast.payer.id)

    response = await cast.payer.post(f"/v1/requests/{request['id']}/pay", json={"paid_on": "2026-10-09"})

    assert response.status_code == 200
    assert response.json()["status"] == "paid"
    assert response.json()["payer"]["id"] == cast.payer.id


async def test_another_payer_cannot_mark_the_payment_of_an_assigned_request(cast: Cast) -> None:
    request = await cast.approved(payer_id=cast.payer.id)

    response = await cast.other_payer.post(f"/v1/requests/{request['id']}/pay", json={"paid_on": "2026-10-09"})

    assert response.status_code == 403
    after = await cast.read(request)
    assert after["status"] == "approved"
    assert after["payer"]["id"] == cast.payer.id


async def test_any_payer_marks_the_payment_of_a_request_assigned_to_nobody(cast: Cast) -> None:
    request = await cast.approved()

    response = await cast.other_payer.post(f"/v1/requests/{request['id']}/pay", json={"paid_on": "2026-10-09"})

    assert response.json()["status"] == "paid"
    assert response.json()["payer"]["id"] == cast.other_payer.id


# --- whose queue ---


async def test_an_assigned_request_stands_in_the_queue_of_its_payer_only(cast: Cast) -> None:
    request = await cast.approved(payer_id=cast.payer.id)

    assert await queue(cast.payer) == [request["id"]]
    assert await queue(cast.other_payer) == []


async def test_a_request_assigned_to_nobody_stands_in_the_queue_of_every_payer(cast: Cast) -> None:
    request = await cast.approved()

    assert await queue(cast.payer) == [request["id"]]
    assert await queue(cast.other_payer) == [request["id"]]


async def test_a_request_is_in_the_queue_of_a_payer_exactly_when_they_may_pay(cast: Cast) -> None:
    requests = [
        await cast.approved(payer_id=cast.payer.id),
        await cast.approved(payer_id=cast.other_payer.id),
        await cast.approved(),
        await cast.submit(payer_id=cast.payer.id),
    ]

    for person in (cast.payer, cast.other_payer):
        may_pay = []
        for request in requests:
            actions = (await person.get(f"/v1/requests/{request['id']}")).json()["actions"]
            if "pay" in actions:
                may_pay.append(request["id"])
        assert await queue(person) == sorted(may_pay)


async def test_the_totals_of_the_queue_count_the_same_requests(cast: Cast) -> None:
    await cast.approved(payer_id=cast.payer.id)
    await cast.approved()

    totals = (await cast.other_payer.get("/v1/request-totals", params={"awaiting_me": True})).json()

    assert {entry["status"]: entry["count"] for entry in totals}["approved"] == 1


# --- the finance director reassigns an approved request ---


async def test_the_finance_director_changes_the_payer_of_an_approved_request(cast: Cast) -> None:
    request = await cast.approved(payer_id=cast.payer.id)

    response = await cast.director.post(
        f"/v1/requests/{request['id']}/reassign", json={"payer_id": cast.other_payer.id}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert response.json()["payer"]["id"] == cast.other_payer.id
    assert await queue(cast.other_payer) == [request["id"]]
    assert await queue(cast.payer) == []


async def test_the_finance_director_leaves_an_approved_request_to_any_payer(cast: Cast) -> None:
    request = await cast.approved(payer_id=cast.payer.id)

    response = await cast.director.post(f"/v1/requests/{request['id']}/reassign", json={"payer_id": None})

    assert response.json()["payer"] is None
    assert await queue(cast.other_payer) == [request["id"]]
    paid = await cast.other_payer.post(f"/v1/requests/{request['id']}/pay", json={"paid_on": "2026-10-09"})
    assert paid.json()["status"] == "paid"


async def test_a_finance_director_reassigns_their_own_request(cast: Cast) -> None:
    author = await cast.world.sign_in("author-director", "requester", "finance_director")
    request = await cast.world.submit(author, cast.lists, cast.moderator)
    await cast.moderator.post(f"/v1/requests/{request['id']}/approve")

    response = await author.post(f"/v1/requests/{request['id']}/reassign", json={"payer_id": cast.payer.id})

    assert response.status_code == 200
    assert response.json()["payer"]["id"] == cast.payer.id


@pytest.mark.parametrize("status", ["new", "paid"])
async def test_a_request_that_is_not_approved_is_not_reassigned(cast: Cast, status: str) -> None:
    request = await cast.submit() if status == "new" else await cast.approved()
    if status == "paid":
        await cast.payer.post(f"/v1/requests/{request['id']}/pay", json={"paid_on": "2026-10-09"})
    payer_before = (await cast.read(request))["payer"]

    response = await cast.director.post(
        f"/v1/requests/{request['id']}/reassign", json={"payer_id": cast.other_payer.id}
    )

    assert response.status_code == 409
    assert response.json()["status"] == status
    assert (await cast.read(request))["payer"] == payer_before


async def test_the_moderator_cannot_reassign(cast: Cast) -> None:
    request = await cast.approved(payer_id=cast.payer.id)

    response = await cast.moderator.post(
        f"/v1/requests/{request['id']}/reassign", json={"payer_id": cast.other_payer.id}
    )

    assert response.status_code == 403
    assert (await cast.read(request))["payer"]["id"] == cast.payer.id


async def test_reassigning_without_the_field_names_it(cast: Cast) -> None:
    request = await cast.approved(payer_id=cast.payer.id)

    response = await cast.director.post(f"/v1/requests/{request['id']}/reassign", json={})

    assert response.status_code == 422
    assert field(response) == ("payer_id", "required")


async def test_reassigning_to_a_person_without_the_role_is_refused(cast: Cast) -> None:
    request = await cast.approved(payer_id=cast.payer.id)

    response = await cast.director.post(f"/v1/requests/{request['id']}/reassign", json={"payer_id": cast.author.id})

    assert response.status_code == 422
    assert field(response) == ("payer_id", "not_a_payer")
    assert (await cast.read(request))["payer"]["id"] == cast.payer.id


async def test_reassigning_is_offered_to_the_finance_director_of_an_approved_request_only(cast: Cast) -> None:
    new = await cast.submit()
    approved = await cast.approved()

    def actions(person: Session, request: dict[str, Any]) -> Any:
        return person.get(f"/v1/requests/{request['id']}")

    assert "reassign" in (await actions(cast.director, approved)).json()["actions"]
    assert "reassign" not in (await actions(cast.director, new)).json()["actions"]
    assert "reassign" not in (await actions(cast.payer, approved)).json()["actions"]
    assert "reassign" not in (await actions(cast.author, approved)).json()["actions"]


# --- the journal names who the request was sent to ---


def payer_change(entry: dict[str, Any]) -> tuple[bool, int | None]:
    """Whether a journal entry changed the payer, and to whom."""
    return entry["payer_changed"], entry["payer"] and entry["payer"]["id"]


async def test_approving_with_a_new_payer_leaves_one_entry_that_names_them(cast: Cast) -> None:
    request = await cast.approved(payer_id=cast.payer.id)

    journal = request["journal"]

    assert [entry["status"] for entry in journal] == ["new", "approved"]
    assert journal[-1]["status_changed"] is True
    assert payer_change(journal[-1]) == (True, cast.payer.id)


async def test_approving_without_a_payer_names_nobody_in_the_journal(cast: Cast) -> None:
    request = await cast.approved()

    assert payer_change(request["journal"][-1]) == (False, None)


async def test_approving_with_the_payer_the_request_has_names_nobody_in_the_journal(cast: Cast) -> None:
    request = await cast.submit(payer_id=cast.payer.id)

    response = await cast.moderator.post(f"/v1/requests/{request['id']}/approve", json={"payer_id": cast.payer.id})

    assert payer_change(response.json()["journal"][-1]) == (False, None)


async def test_reassigning_leaves_an_entry_that_names_the_new_payer(cast: Cast) -> None:
    request = await cast.approved(payer_id=cast.payer.id)

    response = await cast.director.post(
        f"/v1/requests/{request['id']}/reassign", json={"payer_id": cast.other_payer.id}
    )

    journal = response.json()["journal"]
    assert len(journal) == len(request["journal"]) + 1
    assert journal[-1]["person"]["id"] == cast.director.id
    assert journal[-1]["status"] == "approved"
    assert journal[-1]["status_changed"] is False
    assert journal[-1]["comment"] is None
    assert payer_change(journal[-1]) == (True, cast.other_payer.id)


async def test_taking_the_payer_off_leaves_an_entry_without_a_payer(cast: Cast) -> None:
    request = await cast.approved(payer_id=cast.payer.id)

    response = await cast.director.post(f"/v1/requests/{request['id']}/reassign", json={"payer_id": None})

    assert payer_change(response.json()["journal"][-1]) == (True, None)


async def test_reassigning_to_the_same_payer_leaves_an_entry_only_with_a_comment(cast: Cast) -> None:
    request = await cast.approved(payer_id=cast.payer.id)
    url = f"/v1/requests/{request['id']}/reassign"

    silent = (await cast.director.post(url, json={"payer_id": cast.payer.id})).json()["journal"]
    commented = (await cast.director.post(url, json={"payer_id": cast.payer.id, "comment": "Still them"})).json()[
        "journal"
    ]

    assert len(silent) == len(request["journal"])
    assert len(commented) == len(request["journal"]) + 1
    assert commented[-1]["comment"] == "Still them"
    assert payer_change(commented[-1]) == (False, None)


async def test_the_author_naming_a_payer_and_the_payment_change_no_payer_in_the_journal(cast: Cast) -> None:
    request = await cast.submit(payer_id=cast.payer.id)
    await cast.moderator.post(f"/v1/requests/{request['id']}/approve", json={})

    paid = await cast.payer.post(f"/v1/requests/{request['id']}/pay", json={"paid_on": "2026-10-09"})

    assert paid.status_code == 200, paid.text
    assert [payer_change(entry) for entry in paid.json()["journal"]] == [(False, None)] * 3
