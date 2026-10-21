from dataclasses import dataclass

import pytest

from tests.conftest import FakeStorage, Session, World

INVOICE = ("invoice.pdf", b"%PDF-1.7 invoice", "application/pdf")


@dataclass
class Scene:
    author: Session
    moderator: Session
    url: str
    lists: dict[str, int]


@pytest.fixture
async def scene(world: World) -> Scene:
    lists = await world.reference_lists()
    author = await world.sign_in("author", "requester")
    moderator = await world.sign_in("moderator", "moderator")
    request = await world.submit(author, lists, moderator)
    return Scene(author, moderator, f"/v1/requests/{request['id']}", lists)


async def test_the_author_attaches_a_file_and_the_moderator_downloads_it(scene: Scene, storage: FakeStorage) -> None:
    response = await scene.author.post(f"{scene.url}/attachments", files={"file": INVOICE})

    assert response.status_code == 201
    attachment = response.json()
    assert attachment["filename"] == "invoice.pdf"
    assert attachment["content_type"] == "application/pdf"
    assert attachment["size"] == len(INVOICE[1])
    assert len(storage.objects) == 1

    detail = (await scene.moderator.get(scene.url)).json()
    assert [item["id"] for item in detail["attachments"]] == [attachment["id"]]

    download = await scene.moderator.get(f"{scene.url}/attachments/{attachment['id']}")
    assert download.status_code == 200
    assert download.content == INVOICE[1]
    assert download.headers["content-type"] == "application/pdf"
    assert "invoice.pdf" in download.headers["content-disposition"]


async def test_a_file_over_the_installation_limit_is_refused_and_the_limit_is_named(
    scene: Scene, storage: FakeStorage
) -> None:
    too_large = ("scan.png", b"x" * 1025, "image/png")

    response = await scene.author.post(f"{scene.url}/attachments", files={"file": too_large})

    assert response.status_code == 413
    assert response.json()["limit"] == 1024
    assert "1024" in response.json()["detail"]
    assert storage.objects == {}
    assert (await scene.author.get(scene.url)).json()["attachments"] == []


async def test_a_file_exactly_at_the_limit_is_accepted(scene: Scene) -> None:
    at_limit = ("scan.png", b"x" * 1024, "image/png")

    response = await scene.author.post(f"{scene.url}/attachments", files={"file": at_limit})

    assert response.status_code == 201


async def test_the_author_removes_a_file_while_the_request_can_be_edited(scene: Scene, storage: FakeStorage) -> None:
    attachment = (await scene.author.post(f"{scene.url}/attachments", files={"file": INVOICE})).json()

    response = await scene.author.delete(f"{scene.url}/attachments/{attachment['id']}")

    assert response.status_code == 204
    assert storage.objects == {}
    assert (await scene.author.get(scene.url)).json()["attachments"] == []


async def test_files_of_an_approved_request_cannot_be_added_or_removed(
    world: World, scene: Scene, storage: FakeStorage
) -> None:
    director = await world.sign_in("director", "finance_director")
    attachment = (await scene.author.post(f"{scene.url}/attachments", files={"file": INVOICE})).json()
    await scene.moderator.post(f"{scene.url}/approve")
    await director.post(f"{scene.url}/approve")

    added = await scene.author.post(f"{scene.url}/attachments", files={"file": INVOICE})
    removed = await scene.author.delete(f"{scene.url}/attachments/{attachment['id']}")

    assert added.status_code == 409
    assert removed.status_code == 409
    assert added.json()["status"] == "approved"
    assert len(storage.objects) == 1
    assert len((await scene.author.get(scene.url)).json()["attachments"]) == 1


async def test_the_author_attaches_an_invoice_to_a_request_its_payer_returned(world: World, scene: Scene) -> None:
    director = await world.sign_in("director", "finance_director")
    payer = await world.sign_in("payer", "payer")
    await scene.moderator.post(f"{scene.url}/approve")
    await director.post(f"{scene.url}/approve")
    await payer.post(f"{scene.url}/return", json={"comment": "Attach the invoice"})

    response = await scene.author.post(f"{scene.url}/attachments", files={"file": INVOICE})

    assert response.status_code == 201
    assert len((await payer.get(scene.url)).json()["attachments"]) == 1


async def test_only_the_author_changes_the_files(scene: Scene) -> None:
    attachment = (await scene.author.post(f"{scene.url}/attachments", files={"file": INVOICE})).json()

    added = await scene.moderator.post(f"{scene.url}/attachments", files={"file": INVOICE})
    removed = await scene.moderator.delete(f"{scene.url}/attachments/{attachment['id']}")

    assert added.status_code == 403
    assert removed.status_code == 403


async def test_a_file_of_a_request_the_person_cannot_see_looks_like_a_missing_file(world: World, scene: Scene) -> None:
    attachment = (await scene.author.post(f"{scene.url}/attachments", files={"file": INVOICE})).json()
    outsider = await world.sign_in("outsider", "requester")

    hidden = await outsider.get(f"{scene.url}/attachments/{attachment['id']}")
    missing = await outsider.get("/v1/requests/999999/attachments/1")

    assert hidden.status_code == missing.status_code == 404
    assert hidden.json() == missing.json()


async def test_a_file_is_not_served_under_another_request(world: World, scene: Scene) -> None:
    attachment = (await scene.author.post(f"{scene.url}/attachments", files={"file": INVOICE})).json()
    other = await world.submit(scene.author, scene.lists, scene.moderator)

    response = await scene.author.get(f"/v1/requests/{other['id']}/attachments/{attachment['id']}")

    assert response.status_code == 404


async def test_a_moderator_submits_a_request_with_an_invoice_and_the_director_downloads_it(
    world: World, storage: FakeStorage
) -> None:
    lists = await world.reference_lists()
    moderator = await world.sign_in("moderator", "requester", "moderator")
    director = await world.sign_in("director", "finance_director")
    body = world.request_body(lists, moderator, moderator_id=None)

    response = await moderator.create_request(body, files=[INVOICE])

    assert response.status_code == 201, response.text
    created = response.json()
    assert created["status"] == "escalated"
    assert [item["filename"] for item in created["attachments"]] == ["invoice.pdf"]
    assert len(storage.objects) == 1
    assert next(iter(storage.objects)).startswith(f"requests/{created['id']}/")
    url = f"/v1/requests/{created['id']}"
    download = await director.get(f"{url}/attachments/{created['attachments'][0]['id']}")
    assert download.status_code == 200
    assert download.content == INVOICE[1]


async def test_a_requester_submits_a_request_with_two_documents(world: World, storage: FakeStorage) -> None:
    lists = await world.reference_lists()
    author = await world.sign_in("author", "requester")
    moderator = await world.sign_in("moderator", "moderator")
    contract = ("contract.docx", b"PK contract", "application/octet-stream")

    response = await author.create_request(world.request_body(lists, moderator), files=[INVOICE, contract])

    assert response.status_code == 201, response.text
    created = response.json()
    assert created["status"] == "new"
    assert sorted(item["filename"] for item in created["attachments"]) == ["contract.docx", "invoice.pdf"]
    assert len(storage.objects) == 2


async def test_a_new_request_with_a_file_over_the_limit_is_not_created(world: World, storage: FakeStorage) -> None:
    lists = await world.reference_lists()
    author = await world.sign_in("author", "requester")
    moderator = await world.sign_in("moderator", "moderator")
    too_large = ("scan.png", b"x" * 1025, "image/png")

    response = await author.create_request(world.request_body(lists, moderator), files=[INVOICE, too_large])

    assert response.status_code == 413
    assert response.json()["limit"] == 1024
    assert storage.objects == {}
    assert (await author.get("/v1/requests")).json()["total"] == 0


async def test_a_new_request_with_a_missing_field_stores_none_of_its_files(world: World, storage: FakeStorage) -> None:
    lists = await world.reference_lists()
    author = await world.sign_in("author", "requester")
    moderator = await world.sign_in("moderator", "moderator")
    body = world.request_body(lists, moderator)
    del body["situation"]

    response = await author.create_request(body, files=[INVOICE])

    assert response.status_code == 422
    assert [item["loc"][-1] for item in response.json()["detail"]] == ["situation"]
    assert storage.objects == {}
    assert (await author.get("/v1/requests")).json()["total"] == 0


async def test_a_new_request_whose_fields_are_not_json_is_refused(world: World) -> None:
    author = await world.sign_in("author", "requester")

    response = await author.post("/v1/requests", data={"request": "{not json"})

    assert response.status_code == 422
