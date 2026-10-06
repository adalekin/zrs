from typing import Any

import pytest

from tests.conftest import Session, World


def error_fields(body: dict[str, Any]) -> list[str]:
    return [error["loc"][-1] for error in body["detail"]]


@pytest.fixture
async def lists(world: World) -> dict[str, int]:
    return await world.reference_lists()


@pytest.fixture
async def author(world: World) -> Session:
    return await world.sign_in("author", "requester")


@pytest.fixture
async def moderator(world: World) -> Session:
    return await world.sign_in("moderator", "moderator")


# --- submitting ---


async def test_a_requester_submits_a_request(
    world: World, lists: dict[str, int], author: Session, moderator: Session
) -> None:
    response = await author.post("/v1/requests", json=world.request_body(lists, moderator))

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "new"
    assert body["author"]["id"] == author.id
    assert body["moderator"]["id"] == moderator.id
    assert body["amount"] == "1590.0000"
    assert body["payment_form"] is None
    assert body["deadline"] is None
    assert body["payer"] is None


@pytest.mark.parametrize("field", ["situation", "solution", "amount", "currency", "payment_period", "moderator_id"])
async def test_a_request_without_a_required_field_names_the_field(
    world: World, lists: dict[str, int], author: Session, moderator: Session, field: str
) -> None:
    body = world.request_body(lists, moderator)
    del body[field]

    response = await author.post("/v1/requests", json=body)

    assert response.status_code == 422
    assert error_fields(response.json()) == [field]


@pytest.mark.parametrize("field", ["operation_type_id", "priority_id"])
async def test_a_request_without_a_required_reference_value_names_the_field(
    world: World, lists: dict[str, int], author: Session, moderator: Session, field: str
) -> None:
    body = world.request_body(lists, moderator)
    del body[field]

    response = await author.post("/v1/requests", json=body)

    assert response.status_code == 422
    assert error_fields(response.json()) == [field]


async def test_a_blank_situation_counts_as_missing(
    world: World, lists: dict[str, int], author: Session, moderator: Session
) -> None:
    response = await author.post("/v1/requests", json=world.request_body(lists, moderator, situation="   "))

    assert response.status_code == 422
    assert error_fields(response.json()) == ["situation"]


@pytest.mark.parametrize("amount", ["0", "-10", "1.23456"])
async def test_an_amount_that_is_not_positive_or_too_precise_names_the_field(
    world: World, lists: dict[str, int], author: Session, moderator: Session, amount: str
) -> None:
    response = await author.post("/v1/requests", json=world.request_body(lists, moderator, amount=amount))

    assert response.status_code == 422
    assert error_fields(response.json()) == ["amount"]


async def test_a_currency_outside_the_installation_list_names_the_field(
    world: World, lists: dict[str, int], author: Session, moderator: Session
) -> None:
    response = await author.post("/v1/requests", json=world.request_body(lists, moderator, currency="EUR"))

    assert response.status_code == 422
    assert error_fields(response.json()) == ["currency"]
    assert response.json()["detail"][0]["type"] == "currency_not_allowed"


async def test_a_switched_off_operation_type_names_the_field(
    world: World, lists: dict[str, int], author: Session, moderator: Session
) -> None:
    director = await world.sign_in("director", "finance_director")
    await director.patch(f"/v1/reference-items/{lists['operation_type_id']}", json={"is_active": False})
    await world.reference_item("operation_type", "Hosting")

    response = await author.post("/v1/requests", json=world.request_body(lists, moderator))

    assert response.status_code == 422
    assert error_fields(response.json()) == ["operation_type_id"]


async def test_a_value_from_another_reference_list_names_the_field(
    world: World, lists: dict[str, int], author: Session, moderator: Session
) -> None:
    body = world.request_body(lists, moderator, priority_id=lists["operation_type_id"])

    response = await author.post("/v1/requests", json=body)

    assert response.status_code == 422
    assert error_fields(response.json()) == ["priority_id"]


async def test_a_person_without_the_requester_role_cannot_submit(
    world: World, lists: dict[str, int], moderator: Session
) -> None:
    other_moderator = await world.sign_in("other-moderator", "moderator")

    response = await moderator.post("/v1/requests", json=world.request_body(lists, other_moderator))

    assert response.status_code == 403


# --- empty reference lists ---


async def test_submitting_while_the_priority_list_is_empty_names_the_list(
    world: World, author: Session, moderator: Session
) -> None:
    operation_type = await world.reference_item("operation_type", "Advertising")
    body = world.request_body({"operation_type_id": operation_type["id"], "priority_id": 0}, moderator)
    del body["priority_id"]

    response = await author.post("/v1/requests", json=body)

    assert response.status_code == 422
    error = response.json()["detail"][0]
    assert error["loc"][-1] == "priority_id"
    assert error["type"] == "reference_list_empty"
    assert "'priority' has no active values" in error["msg"]


async def test_an_empty_payment_form_list_does_not_block_a_request_without_a_payment_form(
    world: World, author: Session, moderator: Session
) -> None:
    lists = {
        "operation_type_id": (await world.reference_item("operation_type", "Advertising"))["id"],
        "priority_id": (await world.reference_item("priority", "Normal"))["id"],
    }

    response = await author.post("/v1/requests", json=world.request_body(lists, moderator))

    assert response.status_code == 201


# --- choosing the moderator ---


async def test_the_author_cannot_choose_themselves_as_the_moderator(world: World, lists: dict[str, int]) -> None:
    both = await world.sign_in("both", "requester", "moderator")

    response = await both.post("/v1/requests", json=world.request_body(lists, both))

    assert response.status_code == 422
    assert error_fields(response.json()) == ["moderator_id"]


async def test_a_person_without_the_moderator_role_cannot_be_chosen(
    world: World, lists: dict[str, int], author: Session
) -> None:
    payer = await world.sign_in("payer", "payer")

    response = await author.post("/v1/requests", json=world.request_body(lists, payer))

    assert response.status_code == 422
    assert error_fields(response.json()) == ["moderator_id"]


async def test_a_person_who_never_signed_in_cannot_be_chosen(
    world: World, lists: dict[str, int], author: Session, moderator: Session
) -> None:
    body = world.request_body(lists, moderator, moderator_id=moderator.id + 1000)

    response = await author.post("/v1/requests", json=body)

    assert response.status_code == 422
    assert error_fields(response.json()) == ["moderator_id"]


# --- currencies of the installation ---


async def test_a_request_keeps_a_currency_that_left_the_installation_list(
    world: World, lists: dict[str, int], author: Session, moderator: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from internal.config import settings

    request = await world.submit(author, lists, moderator, currency="USD")
    monkeypatch.setattr(settings, "CURRENCIES", ["RUB"])

    assert (await author.get(f"/v1/requests/{request['id']}")).json()["currency"] == "USD"
    assert (await author.get("/v1/me")).json()["currencies"] == ["RUB"]
    refused = await author.post("/v1/requests", json=world.request_body(lists, moderator, currency="USD"))
    assert error_fields(refused.json()) == ["currency"]


# --- editing ---


async def test_the_author_changes_the_amount_of_a_new_request(
    world: World, lists: dict[str, int], author: Session, moderator: Session
) -> None:
    request = await world.submit(author, lists, moderator)

    response = await author.patch(f"/v1/requests/{request['id']}", json={"amount": "2000"})

    assert response.status_code == 200
    assert response.json()["amount"] == "2000.0000"
    assert response.json()["status"] == "new"


async def test_changing_the_moderator_hands_the_request_to_the_new_one(
    world: World, lists: dict[str, int], author: Session, moderator: Session
) -> None:
    second = await world.sign_in("second-moderator", "moderator")
    request = await world.submit(author, lists, moderator)

    response = await author.patch(f"/v1/requests/{request['id']}", json={"moderator_id": second.id})

    assert response.json()["moderator"]["id"] == second.id
    assert (await second.get(f"/v1/requests/{request['id']}")).status_code == 200
    assert (await moderator.get(f"/v1/requests/{request['id']}")).status_code == 404


async def test_the_author_clears_an_optional_field(
    world: World, lists: dict[str, int], author: Session, moderator: Session
) -> None:
    request = await world.submit(
        author, lists, moderator, payment_form_id=lists["payment_form_id"], deadline="2026-12-01"
    )

    response = await author.patch(f"/v1/requests/{request['id']}", json={"payment_form_id": None, "deadline": None})

    assert response.json()["payment_form"] is None
    assert response.json()["deadline"] is None


async def test_a_required_field_cannot_be_cleared(
    world: World, lists: dict[str, int], author: Session, moderator: Session
) -> None:
    request = await world.submit(author, lists, moderator)

    response = await author.patch(f"/v1/requests/{request['id']}", json={"situation": None})

    assert response.status_code == 422
    assert error_fields(response.json()) == ["situation"]


async def test_an_edit_cannot_make_the_author_their_own_moderator(world: World, lists: dict[str, int]) -> None:
    both = await world.sign_in("both", "requester", "moderator")
    moderator = await world.sign_in("moderator", "moderator")
    request = await world.submit(both, lists, moderator)

    response = await both.patch(f"/v1/requests/{request['id']}", json={"moderator_id": both.id})

    assert response.status_code == 422
    assert error_fields(response.json()) == ["moderator_id"]


async def test_an_approved_request_cannot_be_edited(
    world: World, lists: dict[str, int], author: Session, moderator: Session
) -> None:
    request = await world.submit(author, lists, moderator)
    await moderator.post(f"/v1/requests/{request['id']}/approve")

    response = await author.patch(f"/v1/requests/{request['id']}", json={"amount": "1"})

    assert response.status_code == 409
    assert response.json()["status"] == "approved"
    assert (await author.get(f"/v1/requests/{request['id']}")).json()["amount"] == "1590.0000"


async def test_the_moderator_cannot_edit_the_request(
    world: World, lists: dict[str, int], author: Session, moderator: Session
) -> None:
    request = await world.submit(author, lists, moderator)

    response = await moderator.patch(f"/v1/requests/{request['id']}", json={"amount": "1"})

    assert response.status_code == 403
