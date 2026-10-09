import pytest

from tests.conftest import Session, World


async def scene(world: World) -> Session:
    """Six requests of one author, read by a finance director.

    1 normal, no deadline       4 urgent, deadline 9 October
    2 urgent, deadline 15       5 normal, no deadline
    3 normal, deadline 9        6 urgent, deadline 1 October, paid
    """
    lists = await world.reference_lists()
    director = await world.sign_in("director", "finance_director")
    author = await world.sign_in("author", "requester")
    moderator = await world.sign_in("moderator", "moderator")
    payer = await world.sign_in("payer", "payer")

    urgent = (await director.post("/v1/reference-items", json={"kind": "priority", "name": "Urgent"})).json()
    await director.post(f"/v1/reference-items/{urgent['id']}/position", json={"position": 1})
    normal = {"priority_id": lists["priority_id"]}
    first = {"priority_id": urgent["id"]}

    await world.submit(author, lists, moderator, **normal)
    await world.submit(author, lists, moderator, **first, deadline="2026-10-15")
    await world.submit(author, lists, moderator, **normal, deadline="2026-10-09")
    await world.submit(author, lists, moderator, **first, deadline="2026-10-09")
    await world.submit(author, lists, moderator, **normal)
    paid = await world.submit(author, lists, moderator, **first, deadline="2026-10-01")
    await moderator.post(f"/v1/requests/{paid['id']}/approve", json={})
    await payer.post(f"/v1/requests/{paid['id']}/pay", json={"paid_on": "2026-10-02", "amount": "1590.00"})
    return director


async def ids(person: Session, **params: str | int) -> list[int]:
    response = await person.get("/v1/requests", params=params)
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()["items"]]


@pytest.mark.parametrize(
    ("sort", "expected"),
    [
        # By the date of submission a finished request stands where its date puts it.
        ("-created", [6, 5, 4, 3, 2, 1]),
        ("created", [1, 2, 3, 4, 5, 6]),
        # The urgent ones first, among them the nearest deadline; equal ones by who waits longer;
        # a request without a deadline below the ones with it; the paid one below everything.
        ("priority", [4, 2, 3, 1, 5, 6]),
        ("-priority", [3, 1, 5, 4, 2, 6]),
        # One deadline: the urgent one above. No deadline: below, whichever way the order goes.
        ("deadline", [4, 3, 2, 1, 5, 6]),
        ("-deadline", [2, 4, 3, 1, 5, 6]),
    ],
)
async def test_the_list_comes_in_the_asked_order(world: World, sort: str, expected: list[int]) -> None:
    director = await scene(world)

    assert await ids(director, sort=sort) == expected


async def test_without_an_asked_order_the_newest_request_is_first(world: World) -> None:
    director = await scene(world)

    assert await ids(director) == [6, 5, 4, 3, 2, 1]


async def test_the_second_page_continues_the_order_of_the_first(world: World) -> None:
    director = await scene(world)

    pages = [await ids(director, sort="priority", size=2, page=page) for page in (1, 2, 3)]

    assert pages == [[4, 2], [3, 1], [5, 6]]


async def test_the_order_follows_the_place_the_finance_director_gave_a_priority(world: World) -> None:
    director = await scene(world)
    listed = (await director.get("/v1/reference-items", params={"kind": "priority"})).json()
    normal = next(item for item in listed if item["name"] == "Normal")

    await director.post(f"/v1/reference-items/{normal['id']}/position", json={"position": 1})

    assert await ids(director, sort="priority") == [3, 1, 5, 4, 2, 6]


async def test_the_order_applies_to_a_filtered_list(world: World) -> None:
    director = await scene(world)

    assert await ids(director, sort="priority", status="new") == [4, 2, 3, 1, 5]


async def test_an_unknown_order_is_refused(world: World) -> None:
    director = await scene(world)

    response = await director.get("/v1/requests", params={"sort": "amount"})

    assert response.status_code == 422
