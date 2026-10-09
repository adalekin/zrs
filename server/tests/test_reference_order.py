import asyncio

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.conftest import Session, World


async def priorities(person: Session, **params: bool) -> list[tuple[str, int]]:
    listed = (await person.get("/v1/reference-items", params={"kind": "priority", **params})).json()
    return [(item["name"], item["position"]) for item in listed]


async def add(director: Session, name: str, kind: str = "priority") -> dict:
    response = await director.post("/v1/reference-items", json={"kind": kind, "name": name})
    assert response.status_code == 201, response.text
    return response.json()


async def test_a_new_priority_takes_the_last_place(world: World) -> None:
    director = await world.sign_in("director", "finance_director")

    # Named against the alphabet on purpose: the order is the order of adding, not of names.
    for name in ["Urgent", "High", "Normal"]:
        await add(director, name)

    assert await priorities(director) == [("Urgent", 1), ("High", 2), ("Normal", 3)]


async def test_the_lists_without_an_order_come_by_name_and_have_no_place(world: World) -> None:
    director = await world.sign_in("director", "finance_director")
    for name in ["Services", "Advertising"]:
        await add(director, name, kind="operation_type")

    listed = (await director.get("/v1/reference-items", params={"kind": "operation_type"})).json()

    assert [(item["name"], item["position"]) for item in listed] == [("Advertising", None), ("Services", None)]


async def test_the_finance_director_moves_a_priority_to_the_next_place(world: World) -> None:
    director = await world.sign_in("director", "finance_director")
    await add(director, "Normal")
    urgent = await add(director, "Urgent")

    response = await director.post(f"/v1/reference-items/{urgent['id']}/position", json={"position": 1})

    assert response.status_code == 200
    assert response.json()["position"] == 1
    assert await priorities(director) == [("Urgent", 1), ("Normal", 2)]


async def test_a_priority_moves_over_several_places_and_the_ones_between_shift(world: World) -> None:
    director = await world.sign_in("director", "finance_director")
    items = [await add(director, name) for name in ["A", "B", "C", "D"]]

    await director.post(f"/v1/reference-items/{items[3]['id']}/position", json={"position": 1})
    assert await priorities(director) == [("D", 1), ("A", 2), ("B", 3), ("C", 4)]

    await director.post(f"/v1/reference-items/{items[3]['id']}/position", json={"position": 3})
    assert await priorities(director) == [("A", 1), ("B", 2), ("D", 3), ("C", 4)]


@pytest.mark.parametrize("position", [0, 3])
async def test_a_place_the_list_does_not_have_is_refused(world: World, position: int) -> None:
    director = await world.sign_in("director", "finance_director")
    await add(director, "Normal")
    urgent = await add(director, "Urgent")

    response = await director.post(f"/v1/reference-items/{urgent['id']}/position", json={"position": position})

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "position"]
    assert await priorities(director) == [("Normal", 1), ("Urgent", 2)]


async def test_a_value_of_a_list_without_an_order_is_not_moved(world: World) -> None:
    director = await world.sign_in("director", "finance_director")
    await add(director, "Advertising", kind="operation_type")
    services = await add(director, "Services", kind="operation_type")

    response = await director.post(f"/v1/reference-items/{services['id']}/position", json={"position": 1})

    assert response.status_code == 409
    assert response.json()["code"] == "ReferenceListUnordered"
    listed = (await director.get("/v1/reference-items", params={"kind": "operation_type"})).json()
    assert [(item["name"], item["position"]) for item in listed] == [("Advertising", None), ("Services", None)]


@pytest.mark.parametrize("role", ["requester", "moderator", "payer"])
async def test_other_roles_cannot_move_a_priority(world: World, role: str) -> None:
    director = await world.sign_in("director", "finance_director")
    await add(director, "Normal")
    urgent = await add(director, "Urgent")
    person = await world.sign_in("someone", role)

    response = await person.post(f"/v1/reference-items/{urgent['id']}/position", json={"position": 1})

    assert response.status_code == 403
    assert await priorities(person) == [("Normal", 1), ("Urgent", 2)]


async def test_switching_a_priority_off_and_on_keeps_its_place(world: World) -> None:
    director = await world.sign_in("director", "finance_director")
    urgent = await add(director, "Urgent")
    await add(director, "Normal")

    await director.patch(f"/v1/reference-items/{urgent['id']}", json={"is_active": False})
    assert await priorities(director, is_active=True) == [("Normal", 2)]

    await director.patch(f"/v1/reference-items/{urgent['id']}", json={"is_active": True})
    assert await priorities(director) == [("Urgent", 1), ("Normal", 2)]


async def test_a_priority_added_while_another_is_being_added_takes_its_own_place(
    world: World, engine: AsyncEngine
) -> None:
    director = await world.sign_in("director", "finance_director")
    await add(director, "Urgent")

    # A second database session plays the other finance director: it holds the lock on the
    # order of priorities and adds its own value, so the request below is known to arrive
    # while that transaction is open.
    async with engine.connect() as adding:
        transaction = await adding.begin()
        await adding.execute(text("SELECT pg_advisory_xact_lock(hashtext('reference_item.priority.position'))"))

        request = asyncio.create_task(director.post("/v1/reference-items", json={"kind": "priority", "name": "Low"}))
        await asyncio.sleep(0.3)
        assert not request.done(), "adding a priority must wait for the lock on the order"

        await adding.execute(text("INSERT INTO reference_item (kind, name, position) VALUES ('priority', 'Normal', 2)"))
        await transaction.commit()

    response = await request

    assert response.status_code == 201
    assert await priorities(director) == [("Urgent", 1), ("Normal", 2), ("Low", 3)]
