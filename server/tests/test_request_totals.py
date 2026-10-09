from decimal import Decimal

from tests.conftest import Session, World


def by_status(totals: list[dict]) -> dict[str, dict]:
    return {entry["status"]: entry for entry in totals}


def amounts(entry: dict) -> dict[str, Decimal]:
    return {amount["currency"]: Decimal(amount["amount"]) for amount in entry["amounts"]}


async def read(person: Session, **params: bool) -> dict[str, dict]:
    response = await person.get("/v1/request-totals", params=params)
    assert response.status_code == 200, response.text
    return by_status(response.json())


async def test_every_status_is_listed_and_an_empty_one_has_a_zero(world: World) -> None:
    director = await world.sign_in("director", "finance_director")

    response = await director.get("/v1/request-totals")

    assert response.status_code == 200
    assert [entry["status"] for entry in response.json()] == [
        "new",
        "returned",
        "escalated",
        "approved",
        "paid",
        "rejected",
    ]
    assert all(entry == {"status": entry["status"], "count": 0, "amounts": []} for entry in response.json())


async def test_amounts_of_two_currencies_are_summed_apart(world: World) -> None:
    lists = await world.reference_lists()
    director = await world.sign_in("director", "finance_director")
    author = await world.sign_in("author", "requester")
    moderator = await world.sign_in("moderator", "moderator")
    await world.submit(author, lists, moderator, amount="100000.00", currency="RUB")
    await world.submit(author, lists, moderator, amount="76400.50", currency="RUB")
    await world.submit(author, lists, moderator, amount="199.00", currency="USD")

    totals = await read(director)

    assert totals["new"]["count"] == 3
    assert amounts(totals["new"]) == {"RUB": Decimal("176400.50"), "USD": Decimal("199.00")}


async def test_a_request_is_counted_in_the_status_it_has_now(world: World) -> None:
    lists = await world.reference_lists()
    director = await world.sign_in("director", "finance_director")
    author = await world.sign_in("author", "requester")
    moderator = await world.sign_in("moderator", "moderator")
    payer = await world.sign_in("payer", "payer")
    approved = await world.submit(author, lists, moderator, amount="62000.00")
    paid = await world.submit(author, lists, moderator, amount="48000.00")
    await world.submit(author, lists, moderator, amount="1000.00")
    await moderator.post(f"/v1/requests/{approved['id']}/approve", json={})
    await moderator.post(f"/v1/requests/{paid['id']}/approve", json={})
    await payer.post(f"/v1/requests/{paid['id']}/pay", json={"paid_on": "2026-10-08", "amount": "1590.00"})

    totals = await read(director)

    assert {status: entry["count"] for status, entry in totals.items()} == {
        "new": 1,
        "returned": 0,
        "escalated": 0,
        "approved": 1,
        "paid": 1,
        "rejected": 0,
    }
    assert amounts(totals["approved"]) == {"RUB": Decimal("62000.00")}
    assert amounts(totals["paid"]) == {"RUB": Decimal("48000.00")}


async def test_a_requester_gets_the_totals_of_their_own_requests_only(world: World) -> None:
    lists = await world.reference_lists()
    author = await world.sign_in("author", "requester")
    other = await world.sign_in("other", "requester")
    moderator = await world.sign_in("moderator", "moderator")
    await world.submit(author, lists, moderator, amount="500.00")
    await world.submit(other, lists, moderator, amount="900.00")

    totals = await read(author)

    assert totals["new"]["count"] == 1
    assert amounts(totals["new"]) == {"RUB": Decimal("500.00")}


async def test_awaiting_me_counts_the_queue_of_the_person_only(world: World) -> None:
    lists = await world.reference_lists()
    author = await world.sign_in("author", "requester")
    moderator = await world.sign_in("moderator", "moderator")
    director = await world.sign_in("director", "finance_director")
    waiting = await world.submit(author, lists, moderator, amount="300000.00")
    await world.submit(author, lists, moderator, amount="18500.00")
    await moderator.post(f"/v1/requests/{waiting['id']}/escalate", json={})

    everything = await read(director)
    queue = await read(director, awaiting_me=True)

    assert everything["new"]["count"] == 1
    assert queue["new"] == {"status": "new", "count": 0, "amounts": []}
    assert queue["escalated"]["count"] == 1
    assert amounts(queue["escalated"]) == {"RUB": Decimal("300000.00")}
