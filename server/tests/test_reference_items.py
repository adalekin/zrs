import pytest

from tests.conftest import World


async def test_the_finance_director_adds_a_value_and_authors_see_it(world: World) -> None:
    director = await world.sign_in("director", "finance_director")
    author = await world.sign_in("author", "requester")

    response = await director.post("/v1/reference-items", json={"kind": "operation_type", "name": " Advertising "})

    assert response.status_code == 201
    assert response.json()["name"] == "Advertising"
    listed = (await author.get("/v1/reference-items", params={"kind": "operation_type", "is_active": True})).json()
    assert [item["name"] for item in listed] == ["Advertising"]


@pytest.mark.parametrize("role", ["requester", "moderator", "payer"])
async def test_other_roles_cannot_change_reference_lists(world: World, role: str) -> None:
    item = await world.reference_item("priority", "Normal")
    person = await world.sign_in("someone", role)

    created = await person.post("/v1/reference-items", json={"kind": "priority", "name": "Urgent"})
    updated = await person.patch(f"/v1/reference-items/{item['id']}", json={"is_active": False})

    assert created.status_code == 403
    assert updated.status_code == 403


async def test_a_repeated_name_within_one_list_is_refused(world: World) -> None:
    director = await world.sign_in("director", "finance_director")
    await director.post("/v1/reference-items", json={"kind": "payment_form", "name": "Card"})

    response = await director.post("/v1/reference-items", json={"kind": "payment_form", "name": "Card"})

    assert response.status_code == 409
    assert "Card" in response.json()["detail"]


async def test_the_same_name_is_allowed_in_another_list(world: World) -> None:
    director = await world.sign_in("director", "finance_director")
    await director.post("/v1/reference-items", json={"kind": "payment_form", "name": "Other"})

    response = await director.post("/v1/reference-items", json={"kind": "operation_type", "name": "Other"})

    assert response.status_code == 201


async def test_renaming_to_a_name_that_already_exists_is_refused(world: World) -> None:
    director = await world.sign_in("director", "finance_director")
    await director.post("/v1/reference-items", json={"kind": "priority", "name": "Normal"})
    urgent = (await director.post("/v1/reference-items", json={"kind": "priority", "name": "Urgent"})).json()

    response = await director.patch(f"/v1/reference-items/{urgent['id']}", json={"name": "Normal"})

    assert response.status_code == 409


async def test_a_switched_off_value_leaves_the_choice_and_returns_when_switched_on(world: World) -> None:
    director = await world.sign_in("director", "finance_director")
    author = await world.sign_in("author", "requester")
    item = (await director.post("/v1/reference-items", json={"kind": "priority", "name": "Urgent"})).json()

    await director.patch(f"/v1/reference-items/{item['id']}", json={"is_active": False})
    active = (await author.get("/v1/reference-items", params={"kind": "priority", "is_active": True})).json()
    everything = (await director.get("/v1/reference-items", params={"kind": "priority"})).json()
    assert active == []
    assert [entry["is_active"] for entry in everything] == [False]

    await director.patch(f"/v1/reference-items/{item['id']}", json={"is_active": True})
    active = (await author.get("/v1/reference-items", params={"kind": "priority", "is_active": True})).json()
    assert [entry["name"] for entry in active] == ["Urgent"]


async def test_a_renamed_value_shows_its_new_name_in_existing_requests(world: World) -> None:
    lists = await world.reference_lists()
    director = await world.sign_in("director", "finance_director")
    author = await world.sign_in("author", "requester")
    moderator = await world.sign_in("moderator", "moderator")
    request = await world.submit(author, lists, moderator, payment_form_id=lists["payment_form_id"])

    await director.patch(f"/v1/reference-items/{lists['payment_form_id']}", json={"name": "Bank card"})

    assert (await author.get(f"/v1/requests/{request['id']}")).json()["payment_form"]["name"] == "Bank card"


async def test_a_request_keeps_a_value_that_was_switched_off_later(world: World) -> None:
    lists = await world.reference_lists()
    director = await world.sign_in("director", "finance_director")
    author = await world.sign_in("author", "requester")
    moderator = await world.sign_in("moderator", "moderator")
    request = await world.submit(author, lists, moderator)

    await director.patch(f"/v1/reference-items/{lists['operation_type_id']}", json={"is_active": False})

    body = (await author.get(f"/v1/requests/{request['id']}")).json()
    assert body["operation_type"]["name"] == "Advertising"
    assert body["operation_type"]["is_active"] is False


async def test_there_is_no_way_to_delete_a_value(world: World) -> None:
    item = await world.reference_item("priority", "Normal")
    director = await world.sign_in("director", "finance_director")

    response = await director.delete(f"/v1/reference-items/{item['id']}")

    assert response.status_code == 405
