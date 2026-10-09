from dataclasses import dataclass

import pytest
from httpx import AsyncClient

from tests.conftest import Session, World


@dataclass
class Scene:
    author: Session
    moderator: Session
    finance_director: Session
    payer: Session
    url: str


@pytest.fixture
async def scene(world: World) -> Scene:
    lists = await world.reference_lists()
    author = await world.sign_in("author", "requester", name="Ann Author")
    moderator = await world.sign_in("moderator", "moderator", name="Max Moderator")
    finance_director = await world.sign_in("director", "finance_director")
    payer = await world.sign_in("payer", "payer", name="Pat Payer")
    request = await world.submit(author, lists, moderator)
    return Scene(author, moderator, finance_director, payer, f"/v1/requests/{request['id']}")


async def test_submitting_writes_the_first_entry(scene: Scene) -> None:
    journal = (await scene.author.get(scene.url)).json()["journal"]

    assert len(journal) == 1
    entry = journal[0]
    assert entry["status"] == "new"
    assert entry["status_changed"] is True
    assert entry["person"]["name"] == "Ann Author"
    assert entry["comment"] is None
    assert entry["created_at"]


async def test_a_decision_with_a_comment_keeps_the_comment(scene: Scene) -> None:
    response = await scene.moderator.post(f"{scene.url}/return", json={"comment": "Attach the invoice"})

    entry = response.json()["journal"][-1]
    assert entry["status"] == "returned"
    assert entry["person"]["name"] == "Max Moderator"
    assert entry["comment"] == "Attach the invoice"


async def test_a_decision_without_a_comment_has_no_text(scene: Scene) -> None:
    await scene.moderator.post(f"{scene.url}/escalate")

    response = await scene.finance_director.post(f"{scene.url}/approve")

    entry = response.json()["journal"][-1]
    assert entry["status"] == "approved"
    assert entry["comment"] is None


async def test_a_payer_comments_without_changing_the_status(scene: Scene) -> None:
    await scene.moderator.post(f"{scene.url}/approve")

    response = await scene.payer.post(f"{scene.url}/comments", json={"comment": "Paying by card tomorrow"})

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "approved"
    entry = body["journal"][-1]
    assert entry["status"] == "approved"
    assert entry["status_changed"] is False
    assert entry["comment"] == "Paying by card tomorrow"
    assert entry["person"]["name"] == "Pat Payer"


async def test_the_author_comments_on_a_paid_request(scene: Scene) -> None:
    await scene.moderator.post(f"{scene.url}/approve")
    await scene.payer.post(f"{scene.url}/pay", json={"paid_on": "2026-10-01", "amount": "1590.00"})

    response = await scene.author.post(f"{scene.url}/comments", json={"comment": "Received, thanks"})

    assert response.status_code == 201
    assert response.json()["status"] == "paid"
    assert response.json()["journal"][-1]["comment"] == "Received, thanks"


@pytest.mark.parametrize("comment", ["", "   "])
async def test_an_empty_comment_is_refused(scene: Scene, comment: str) -> None:
    response = await scene.author.post(f"{scene.url}/comments", json={"comment": comment})

    assert response.status_code == 422
    assert len((await scene.author.get(scene.url)).json()["journal"]) == 1


async def test_a_comment_on_a_request_the_person_cannot_see_looks_like_a_missing_request(
    world: World, scene: Scene
) -> None:
    outsider = await world.sign_in("outsider", "requester")

    hidden = await outsider.post(f"{scene.url}/comments", json={"comment": "Hello"})
    missing = await outsider.post("/v1/requests/999999/comments", json={"comment": "Hello"})

    assert hidden.status_code == missing.status_code == 404
    assert hidden.json() == missing.json()
    assert len((await scene.author.get(scene.url)).json()["journal"]) == 1


async def test_the_journal_is_shown_oldest_first(scene: Scene) -> None:
    await scene.author.post(f"{scene.url}/comments", json={"comment": "Urgent, please"})
    await scene.moderator.post(f"{scene.url}/escalate", json={"comment": "Over my limit"})
    await scene.finance_director.post(f"{scene.url}/approve")

    journal = (await scene.moderator.get(scene.url)).json()["journal"]

    assert [(entry["status"], entry["status_changed"]) for entry in journal] == [
        ("new", True),
        ("new", False),
        ("escalated", True),
        ("approved", True),
    ]
    assert [entry["created_at"] for entry in journal] == sorted(entry["created_at"] for entry in journal)


async def test_the_api_offers_no_way_to_change_or_delete_a_journal_entry(scene: Scene, client: AsyncClient) -> None:
    entry_id = (await scene.author.get(scene.url)).json()["journal"][0]["id"]
    paths = (await client.get("/openapi.json")).json()["paths"]

    assert not [path for path in paths if "journal" in path]
    assert set(paths["/v1/requests/{request_id}/comments"]) == {"post"}
    assert (await scene.author.patch(f"{scene.url}/comments", json={"comment": "Edited"})).status_code == 405
    assert (await scene.finance_director.delete(f"{scene.url}/comments")).status_code == 405
    assert (await scene.finance_director.delete(f"{scene.url}/comments/{entry_id}")).status_code == 404
    assert len((await scene.author.get(scene.url)).json()["journal"]) == 1
