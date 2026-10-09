"""The periods of a recurring request: where one starts and where the next one does."""

import datetime

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from internal.entity.recurrence import Recurrence

day = datetime.date


@pytest.mark.parametrize(
    ("recurrence", "of", "start", "following"),
    [
        # 9 October 2026 is a Friday.
        (Recurrence.WEEK, day(2026, 10, 9), day(2026, 10, 5), day(2026, 10, 12)),
        (Recurrence.WEEK, day(2026, 10, 11), day(2026, 10, 5), day(2026, 10, 12)),
        (Recurrence.WEEK, day(2026, 10, 12), day(2026, 10, 12), day(2026, 10, 19)),
        # A week that lies in two years starts in the old one.
        (Recurrence.WEEK, day(2027, 1, 1), day(2026, 12, 28), day(2027, 1, 4)),
        (Recurrence.MONTH, day(2026, 10, 12), day(2026, 10, 1), day(2026, 11, 1)),
        (Recurrence.MONTH, day(2026, 10, 1), day(2026, 10, 1), day(2026, 11, 1)),
        (Recurrence.MONTH, day(2026, 12, 31), day(2026, 12, 1), day(2027, 1, 1)),
        (Recurrence.QUARTER, day(2026, 10, 12), day(2026, 10, 1), day(2027, 1, 1)),
        (Recurrence.QUARTER, day(2026, 6, 30), day(2026, 4, 1), day(2026, 7, 1)),
        (Recurrence.QUARTER, day(2026, 1, 1), day(2026, 1, 1), day(2026, 4, 1)),
        (Recurrence.YEAR, day(2026, 10, 12), day(2026, 1, 1), day(2027, 1, 1)),
        (Recurrence.YEAR, day(2028, 2, 29), day(2028, 1, 1), day(2029, 1, 1)),
    ],
)
def test_a_period_starts_and_is_followed(
    recurrence: Recurrence, of: datetime.date, start: datetime.date, following: datetime.date
) -> None:
    assert recurrence.period_start(of) == start
    assert recurrence.next_period_start(of) == following


@pytest.mark.parametrize("recurrence", list(Recurrence))
async def test_the_database_starts_a_period_on_the_same_day(recurrence: Recurrence, engine: AsyncEngine) -> None:
    # The queue of a payer is a query: it must agree with the answer a request is given.
    days = [day(2026, 1, 1) + datetime.timedelta(days=offset) for offset in range(0, 800, 3)]

    async with engine.connect() as connection:
        for of in days:
            in_database = await connection.scalar(
                text("SELECT date_trunc(:unit, CAST(:day AS timestamp))::date"), {"unit": recurrence.value, "day": of}
            )
            assert in_database == recurrence.period_start(of), of
