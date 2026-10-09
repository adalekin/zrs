import pytest

from tests.conftest import Session, World


@pytest.fixture
async def lists(world: World) -> dict[str, int]:
    return await world.reference_lists()


async def ids(session: Session, **params: object) -> list[int]:
    response = await session.get("/v1/requests", params=params)
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()["items"]]


# --- visibility ---


async def test_another_author_request_looks_like_a_missing_one(world: World, lists: dict[str, int]) -> None:
    author = await world.sign_in("author", "requester")
    moderator = await world.sign_in("moderator", "moderator")
    outsider = await world.sign_in("outsider", "requester")
    request = await world.submit(author, lists, moderator)

    hidden = await outsider.get(f"/v1/requests/{request['id']}")
    missing = await outsider.get("/v1/requests/999999")

    assert hidden.status_code == missing.status_code == 404
    assert hidden.json() == missing.json()
    assert await ids(outsider) == []


async def test_a_moderator_does_not_see_a_request_assigned_to_another_moderator(
    world: World, lists: dict[str, int]
) -> None:
    author = await world.sign_in("author", "requester")
    chosen = await world.sign_in("chosen", "moderator")
    other = await world.sign_in("other", "moderator")
    request = await world.submit(author, lists, chosen)

    assert (await other.get(f"/v1/requests/{request['id']}")).status_code == 404
    assert (await other.post(f"/v1/requests/{request['id']}/approve")).status_code == 404
    assert (await other.patch(f"/v1/requests/{request['id']}", json={"amount": "1"})).status_code == 404
    assert await ids(other) == []
    assert await ids(chosen) == [request["id"]]


async def test_a_person_with_two_roles_sees_what_each_role_gives(world: World, lists: dict[str, int]) -> None:
    both = await world.sign_in("both", "requester", "moderator")
    author = await world.sign_in("author", "requester")
    moderator = await world.sign_in("moderator", "moderator")
    own = await world.submit(both, lists, moderator)
    assigned = await world.submit(author, lists, both)
    await world.submit(author, lists, moderator)

    assert sorted(await ids(both)) == sorted([own["id"], assigned["id"]])


@pytest.mark.parametrize("role", ["finance_director", "payer"])
async def test_a_finance_director_and_a_payer_see_every_request(world: World, lists: dict[str, int], role: str) -> None:
    author = await world.sign_in("author", "requester")
    moderator = await world.sign_in("moderator", "moderator")
    viewer = await world.sign_in("viewer", role)
    first = await world.submit(author, lists, moderator)
    second = await world.submit(author, lists, moderator)

    assert await ids(viewer) == [second["id"], first["id"]]
    assert (await viewer.get(f"/v1/requests/{first['id']}")).status_code == 200


async def test_seeing_a_request_without_the_right_to_act_is_not_answered_as_missing(
    world: World, lists: dict[str, int]
) -> None:
    author = await world.sign_in("author", "requester")
    moderator = await world.sign_in("moderator", "moderator")
    payer = await world.sign_in("payer", "payer")
    request = await world.submit(author, lists, moderator)

    response = await payer.post(f"/v1/requests/{request['id']}/approve")

    assert response.status_code == 403


# --- lists ---


async def test_requests_are_listed_newest_first_and_paged(world: World, lists: dict[str, int]) -> None:
    author = await world.sign_in("author", "requester")
    moderator = await world.sign_in("moderator", "moderator")
    created = [(await world.submit(author, lists, moderator))["id"] for _ in range(5)]

    first_page = (await author.get("/v1/requests", params={"size": 2})).json()
    third_page = (await author.get("/v1/requests", params={"size": 2, "page": 3})).json()

    assert first_page["total"] == 5
    assert [item["id"] for item in first_page["items"]] == [created[4], created[3]]
    assert [item["id"] for item in third_page["items"]] == [created[0]]


async def test_the_status_filter(world: World, lists: dict[str, int]) -> None:
    author = await world.sign_in("author", "requester")
    moderator = await world.sign_in("moderator", "moderator")
    director = await world.sign_in("director", "finance_director")
    payer = await world.sign_in("payer", "payer")
    paid = await world.submit(author, lists, moderator)
    await world.submit(author, lists, moderator)
    await moderator.post(f"/v1/requests/{paid['id']}/approve")
    await payer.post(f"/v1/requests/{paid['id']}/pay", json={"paid_on": "2026-10-01", "amount": "1590.00"})

    assert await ids(director, status="paid") == [paid["id"]]


async def test_the_queue_of_each_role(world: World, lists: dict[str, int]) -> None:
    author = await world.sign_in("author", "requester")
    moderator = await world.sign_in("moderator", "moderator")
    other_moderator = await world.sign_in("other-moderator", "moderator")
    director = await world.sign_in("director", "finance_director")
    payer = await world.sign_in("payer", "payer")

    new = await world.submit(author, lists, moderator)
    for_other = await world.submit(author, lists, other_moderator)
    returned = await world.submit(author, lists, moderator)
    escalated = await world.submit(author, lists, moderator)
    approved = await world.submit(author, lists, moderator)
    await moderator.post(f"/v1/requests/{returned['id']}/return")
    await moderator.post(f"/v1/requests/{escalated['id']}/escalate")
    await moderator.post(f"/v1/requests/{approved['id']}/approve")

    assert await ids(author, awaiting_me=True) == [returned["id"]]
    assert await ids(moderator, awaiting_me=True) == [new["id"]]
    assert await ids(other_moderator, awaiting_me=True) == [for_other["id"]]
    assert await ids(director, awaiting_me=True) == [escalated["id"]]
    assert await ids(payer, awaiting_me=True) == [approved["id"]]


async def test_the_queue_of_a_person_with_two_roles_joins_both(world: World, lists: dict[str, int]) -> None:
    author = await world.sign_in("author", "requester")
    moderator = await world.sign_in("moderator", "moderator")
    both = await world.sign_in("both", "finance_director", "payer")
    escalated = await world.submit(author, lists, moderator)
    approved = await world.submit(author, lists, moderator)
    await world.submit(author, lists, moderator)
    await moderator.post(f"/v1/requests/{escalated['id']}/escalate")
    await moderator.post(f"/v1/requests/{approved['id']}/approve")

    assert sorted(await ids(both, awaiting_me=True)) == sorted([escalated["id"], approved["id"]])


async def test_a_finance_director_queue_leaves_out_their_own_and_moderated_requests(
    world: World, lists: dict[str, int]
) -> None:
    director = await world.sign_in("director", "requester", "moderator", "finance_director")
    author = await world.sign_in("author", "requester")
    moderator = await world.sign_in("moderator", "moderator")

    own = await world.submit(director, lists, moderator)
    moderated = await world.submit(author, lists, director)
    foreign = await world.submit(author, lists, moderator)
    await moderator.post(f"/v1/requests/{own['id']}/escalate")
    await director.post(f"/v1/requests/{moderated['id']}/escalate")
    await moderator.post(f"/v1/requests/{foreign['id']}/escalate")

    assert await ids(director, awaiting_me=True) == [foreign["id"]]
