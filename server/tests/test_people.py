from httpx import AsyncClient

from tests.conftest import FakeVerifier, World


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_a_request_without_a_token_is_refused(client: AsyncClient) -> None:
    response = await client.get("/v1/me")

    assert response.status_code == 401


async def test_a_request_with_an_unknown_token_is_refused(client: AsyncClient) -> None:
    response = await client.get("/v1/me", headers=bearer("not-issued"))

    assert response.status_code == 401


async def test_a_person_without_roles_has_no_access_and_is_not_recorded(
    client: AsyncClient, verifier: FakeVerifier, world: World
) -> None:
    token = verifier.issue("stranger", "Stranger", [])

    response = await client.get("/v1/me", headers=bearer(token))

    assert response.status_code == 403
    assert verifier.userinfo_calls == 0
    director = await world.sign_in("director", "finance_director")
    assert (await director.get("/v1/users", params={"role": "requester"})).json() == []


async def test_a_person_whose_roles_are_all_outside_the_mapping_has_no_access(
    client: AsyncClient, verifier: FakeVerifier
) -> None:
    token = verifier.issue("other-app-admin", "Other", ["admin", "viewer"])

    response = await client.get("/v1/me", headers=bearer(token))

    assert response.status_code == 403


async def test_me_reports_the_person_their_roles_and_the_installation_lists(world: World) -> None:
    alice = await world.sign_in("alice", "requester", "moderator", name="Alice Example")

    body = (await alice.get("/v1/me")).json()

    assert body["name"] == "Alice Example"
    assert body["email"] == "alice@example.test"
    assert body["roles"] == ["moderator", "requester"]
    assert body["currencies"] == ["RUB", "USD"]
    assert body["attachment_max_bytes"] == 1024
    assert body["payment_day"] == {"ends_at": "16:30", "timezone": "Europe/Moscow"}


async def test_a_moderator_appears_in_the_list_after_the_first_sign_in(world: World) -> None:
    author = await world.sign_in("author", "requester")
    assert (await author.get("/v1/users", params={"role": "moderator"})).json() == []

    moderator = await world.sign_in("moderator", "moderator", name="Mod Erator")

    people = (await author.get("/v1/users", params={"role": "moderator"})).json()
    assert people == [{"id": moderator.id, "name": "Mod Erator", "email": "moderator@example.test"}]


async def test_a_person_without_the_moderator_role_is_not_in_the_moderator_list(world: World) -> None:
    author = await world.sign_in("author", "requester")
    await world.sign_in("payer", "payer")

    assert (await author.get("/v1/users", params={"role": "moderator"})).json() == []


async def test_a_repeated_request_with_the_same_token_does_not_ask_the_provider_again(
    world: World, verifier: FakeVerifier
) -> None:
    alice = await world.sign_in("alice", "requester")
    calls_after_sign_in = verifier.userinfo_calls

    await alice.get("/v1/me")
    await alice.get("/v1/me")

    assert verifier.userinfo_calls == calls_after_sign_in


async def test_a_new_token_without_the_moderator_role_removes_the_person_from_the_list(world: World) -> None:
    author = await world.sign_in("author", "requester")
    await world.sign_in("mod", "moderator")

    again = await world.sign_in("mod", "requester")

    assert (await author.get("/v1/users", params={"role": "moderator"})).json() == []
    assert (await again.get("/v1/me")).json()["roles"] == ["requester"]


async def test_a_new_token_with_no_roles_at_all_removes_the_person_from_the_list(
    client: AsyncClient, world: World, verifier: FakeVerifier
) -> None:
    author = await world.sign_in("author", "requester")
    await world.sign_in("mod", "moderator")

    token = verifier.issue("mod", "Mod", [])
    response = await client.get("/v1/me", headers=bearer(token))

    assert response.status_code == 403
    assert (await author.get("/v1/users", params={"role": "moderator"})).json() == []


async def test_a_known_person_keeps_working_while_userinfo_is_down(world: World, verifier: FakeVerifier) -> None:
    await world.sign_in("alice", "requester", name="Alice Example")
    verifier.userinfo_available = False
    token = verifier.issue("alice", "Alice Renamed", ["requester"])

    response = await world.client.get("/v1/me", headers=bearer(token))

    assert response.status_code == 200
    assert response.json()["name"] == "Alice Example"

    # Nothing was saved for that token, so the next request asks the provider again.
    verifier.userinfo_available = True
    response = await world.client.get("/v1/me", headers=bearer(token))
    assert response.json()["name"] == "Alice Renamed"


async def test_a_new_person_gets_service_unavailable_while_userinfo_is_down(
    client: AsyncClient, verifier: FakeVerifier, world: World
) -> None:
    verifier.userinfo_available = False
    token = verifier.issue("newcomer", "New Comer", ["moderator"])

    response = await client.get("/v1/me", headers=bearer(token))

    assert response.status_code == 503
    verifier.userinfo_available = True
    author = await world.sign_in("author", "requester")
    assert (await author.get("/v1/users", params={"role": "moderator"})).json() == []


async def test_a_new_person_whose_provider_reports_no_name_gets_service_unavailable(
    client: AsyncClient, verifier: FakeVerifier
) -> None:
    token = verifier.issue("nameless", None, ["requester"])

    response = await client.get("/v1/me", headers=bearer(token))

    assert response.status_code == 503


async def test_userinfo_for_another_subject_is_not_used(client: AsyncClient, verifier: FakeVerifier) -> None:
    token = verifier.issue("mallory", "Mallory", ["requester"])
    verifier._userinfo[token]["sub"] = "someone-else"

    response = await client.get("/v1/me", headers=bearer(token))

    assert response.status_code == 401
