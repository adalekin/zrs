import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.conftest import World


async def test_an_approval_that_arrives_while_the_author_cancels_is_refused(world: World, engine: AsyncEngine) -> None:
    lists = await world.reference_lists()
    author = await world.sign_in("author", "requester")
    moderator = await world.sign_in("moderator", "moderator")
    request = await world.submit(author, lists, moderator)
    url = f"/v1/requests/{request['id']}"

    # A second database session plays the author's cancellation and holds the row lock,
    # so the moderator's approval is known to arrive while that transaction is open.
    async with engine.connect() as cancelling:
        transaction = await cancelling.begin()
        await cancelling.execute(
            text("SELECT id FROM expense_request WHERE id = :id FOR UPDATE"), {"id": request["id"]}
        )

        approval = asyncio.create_task(moderator.post(f"{url}/approve"))
        await asyncio.sleep(0.3)
        assert not approval.done(), "the approval must wait for the row lock"

        await cancelling.execute(
            text("UPDATE expense_request SET status = 'rejected' WHERE id = :id"), {"id": request["id"]}
        )
        await transaction.commit()

    response = await approval

    assert response.status_code == 409
    assert response.json()["status"] == "rejected"
    body = (await author.get(url)).json()
    assert body["status"] == "rejected"
    assert [entry["status"] for entry in body["journal"]] == ["new"]


async def test_two_decisions_sent_at_once_end_in_exactly_one_of_them(world: World) -> None:
    lists = await world.reference_lists()
    author = await world.sign_in("author", "requester")
    moderator = await world.sign_in("moderator", "moderator")

    # Approval and rejection both start from "new" only, so whichever comes second finds
    # the request already decided. A cancellation would not do here: the author may still
    # cancel an approved request, and both actions would succeed one after the other.
    # Repeated, because the order in which the two arrive is up to the scheduler.
    for _ in range(10):
        request = await world.submit(author, lists, moderator)
        url = f"/v1/requests/{request['id']}"

        approved, rejected = await asyncio.gather(moderator.post(f"{url}/approve"), moderator.post(f"{url}/reject"))

        assert sorted([approved.status_code, rejected.status_code]) == [200, 409]
        winner = "approved" if approved.status_code == 200 else "rejected"
        loser = rejected if winner == "approved" else approved
        assert loser.json()["status"] == winner
        body = (await author.get(url)).json()
        assert body["status"] == winner
        assert [entry["status"] for entry in body["journal"]] == ["new", winner]


async def test_a_cancellation_that_loses_to_an_approval_still_cancels(world: World) -> None:
    lists = await world.reference_lists()
    author = await world.sign_in("author", "requester")
    moderator = await world.sign_in("moderator", "moderator")

    # The author may cancel until the request is paid, so both orders are valid; what
    # must hold is that the journal tells the order the two actions were applied in.
    for _ in range(10):
        request = await world.submit(author, lists, moderator)
        url = f"/v1/requests/{request['id']}"

        approved, cancelled = await asyncio.gather(moderator.post(f"{url}/approve"), author.post(f"{url}/cancel"))

        assert cancelled.status_code == 200
        body = (await author.get(url)).json()
        assert body["status"] == "rejected"
        journal = [entry["status"] for entry in body["journal"]]
        if approved.status_code == 200:
            assert journal == ["new", "approved", "rejected"]
        else:
            assert approved.status_code == 409
            assert journal == ["new", "rejected"]
