"""Who rejected a request: the person and what they were to the request when they did."""

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.conftest import Session, World

MIGRATION = Path(__file__).parent.parent / "migrations" / "versions" / "0005_request_rejected_by.py"


@dataclass
class Cast:
    world: World
    lists: dict[str, int]
    author: Session
    moderator: Session
    director: Session

    async def submit(self) -> dict[str, Any]:
        return await self.world.submit(self.author, self.lists, self.moderator)

    async def act(self, person: Session, request: dict[str, Any], action: str) -> dict[str, Any]:
        response = await person.post(f"/v1/requests/{request['id']}/{action}", json={})
        assert response.status_code == 200, response.text
        return response.json()

    async def listed(self, request: dict[str, Any]) -> dict[str, Any]:
        """The request as the list of the finance director gives it."""
        page = (await self.director.get("/v1/requests", params={"size": 100})).json()
        return next(item for item in page["items"] if item["id"] == request["id"])


@pytest.fixture
async def cast(world: World) -> Cast:
    return Cast(
        world=world,
        lists=await world.reference_lists(),
        author=await world.sign_in("author", "requester"),
        moderator=await world.sign_in("moderator", "moderator"),
        director=await world.sign_in("director", "finance_director"),
    )


def rejection(request: dict[str, Any]) -> tuple[int | None, str | None]:
    """Who rejected the request and as what."""
    return request["rejected_by"] and request["rejected_by"]["id"], request["rejected_as"]


async def test_a_request_rejected_by_its_moderator_names_them(cast: Cast) -> None:
    request = await cast.submit()

    rejected = await cast.act(cast.moderator, request, "reject")

    assert rejected["status"] == "rejected"
    assert rejection(rejected) == (cast.moderator.id, "moderator")
    assert rejection(await cast.listed(request)) == (cast.moderator.id, "moderator")


async def test_a_request_rejected_by_the_finance_director_names_them(cast: Cast) -> None:
    request = await cast.submit()
    await cast.act(cast.moderator, request, "escalate")

    rejected = await cast.act(cast.director, request, "reject")

    assert rejection(rejected) == (cast.director.id, "finance_director")
    assert rejection(await cast.listed(request)) == (cast.director.id, "finance_director")


async def test_a_request_cancelled_by_its_author_names_them(cast: Cast) -> None:
    request = await cast.submit()

    cancelled = await cast.act(cast.author, request, "cancel")

    assert cancelled["status"] == "rejected"
    assert rejection(cancelled) == (cast.author.id, "author")
    assert rejection(await cast.listed(request)) == (cast.author.id, "author")


async def test_a_request_that_is_not_rejected_names_nobody(cast: Cast) -> None:
    request = await cast.submit()

    approved = await cast.act(cast.moderator, request, "approve")

    assert rejection(request) == (None, None)
    assert rejection(approved) == (None, None)
    assert rejection(await cast.listed(request)) == (None, None)


async def test_the_migration_names_who_rejected_the_requests_rejected_before_it(
    cast: Cast, engine: AsyncEngine
) -> None:
    by_moderator = await cast.submit()
    by_director = await cast.submit()
    by_author = await cast.submit()
    untouched = await cast.submit()
    await cast.act(cast.moderator, by_moderator, "reject")
    await cast.act(cast.moderator, by_director, "escalate")
    await cast.act(cast.director, by_director, "reject")
    await cast.act(cast.moderator, by_author, "return")
    await cast.act(cast.author, by_author, "cancel")
    # A comment after the rejection is the last entry of the journal, and it rejected nothing.
    await cast.director.post(f"/v1/requests/{by_moderator['id']}/comments", json={"comment": "Noted"})
    spec = importlib.util.spec_from_file_location("migration_0005", MIGRATION)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    async with engine.begin() as connection:
        await connection.execute(text("UPDATE expense_request SET rejected_by_id = NULL, rejected_as = NULL"))
        await connection.execute(text(migration.FILL_REJECTED_BY))

    assert rejection(await cast.listed(by_moderator)) == (cast.moderator.id, "moderator")
    assert rejection(await cast.listed(by_director)) == (cast.director.id, "finance_director")
    assert rejection(await cast.listed(by_author)) == (cast.author.id, "author")
    assert rejection(await cast.listed(untouched)) == (None, None)
