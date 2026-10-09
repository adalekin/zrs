"""One rule of the queue read both ways: the requests that wait for a person, the people a request waits for."""

import datetime

import approck_sqlalchemy_utils.session
from sqlalchemy import select

from internal.entity.expense_request import ExpenseRequest
from internal.service.notification import NotificationService
from tests.conftest import Clock, Session, World

day = datetime.date


async def awaited_people(today: datetime.date) -> dict[int, frozenset[int]]:
    """For every request, the people it waits for."""
    async with approck_sqlalchemy_utils.session.context_session() as session:
        notifications = NotificationService(session)
        requests = (await session.scalars(select(ExpenseRequest))).unique().all()
        return {request.id: await notifications.awaited(request, today) for request in requests}


async def test_a_person_is_awaited_by_a_request_exactly_when_it_is_in_their_queue(world: World, clock: Clock) -> None:
    lists = await world.reference_lists()
    author = await world.sign_in("author", "requester")
    moderator = await world.sign_in("moderator", "moderator")
    other_moderator = await world.sign_in("other-moderator", "moderator", "requester")
    director = await world.sign_in("director", "finance_director")
    director_and_payer = await world.sign_in("director-payer", "finance_director", "payer")
    payer = await world.sign_in("payer", "payer")
    other_payer = await world.sign_in("other-payer", "payer")
    everything = await world.sign_in("everything", "requester", "moderator", "finance_director", "payer")
    people = [author, moderator, other_moderator, director, director_and_payer, payer, other_payer, everything]

    async def act(person: Session, request: dict, action: str, **body: object) -> None:
        response = await person.post(f"/v1/requests/{request['id']}/{action}", json=body)
        assert response.status_code == 200, response.text

    async def submit(by: Session = author, to: Session = moderator, **fields: object) -> dict:
        return await world.submit(by, lists, to, **fields)

    # Every status, with a payer and without, paid once and every period, authors and moderators of their own.
    await submit()
    await submit(by=everything, to=other_moderator)
    await submit(by=other_moderator, to=everything)
    returned = await submit()
    await act(moderator, returned, "return")
    for by, to in ((author, moderator), (everything, moderator), (author, everything)):
        escalated = await submit(by=by, to=to)
        await act(to, escalated, "escalate")
    approved = await submit()
    await act(moderator, approved, "approve")
    assigned = await submit(payer_id=payer.id)
    await act(moderator, assigned, "approve")
    for recurrence, paid_on in (
        ("month", None),
        ("month", "2026-10-06"),
        ("week", "2026-10-06"),
        ("quarter", "2026-09-30"),
    ):
        recurring = await submit(recurrence=recurrence)
        await act(moderator, recurring, "approve")
        if paid_on:
            await act(payer, recurring, "pay", paid_on=paid_on, amount="100")
    recurring_assigned = await submit(recurrence="month", payer_id=other_payer.id)
    await act(moderator, recurring_assigned, "approve")
    await act(other_payer, recurring_assigned, "pay", paid_on="2026-10-06", amount="100")
    paid = await submit()
    await act(moderator, paid, "approve")
    await act(payer, paid, "pay", paid_on="2026-10-06", amount="100")
    rejected = await submit()
    await act(moderator, rejected, "reject")

    for today in (day(2026, 10, 9), day(2026, 10, 12), day(2026, 11, 1), day(2027, 1, 1)):
        clock.today = today
        awaited = await awaited_people(today)
        assert len(awaited) == 16
        for person in people:
            page = (await person.get("/v1/requests", params={"awaiting_me": True, "size": 100})).json()
            queue = {item["id"] for item in page["items"]}
            told = {request_id for request_id, waited_for in awaited.items() if person.id in waited_for}
            assert told == queue, (today, person.id)
        assert any(awaited.values())
