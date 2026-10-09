import datetime
from enum import StrEnum


class Recurrence(StrEnum):
    """How often a request is paid: once in every calendar period of this length.

    The values are the units PostgreSQL's ``date_trunc`` takes, so a query finds the start
    of a period by the same name. A week starts on Monday, there as here.
    """

    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"

    def period_start(self, day: datetime.date) -> datetime.date:
        """The first day of the period this day falls in."""
        match self:
            case Recurrence.WEEK:
                return day - datetime.timedelta(days=day.weekday())
            case Recurrence.MONTH:
                return day.replace(day=1)
            case Recurrence.QUARTER:
                return day.replace(month=(day.month - 1) // 3 * 3 + 1, day=1)
            case Recurrence.YEAR:
                return day.replace(month=1, day=1)

    def next_period_start(self, day: datetime.date) -> datetime.date:
        """The first day of the period after the one this day falls in."""
        start = self.period_start(day)
        match self:
            case Recurrence.WEEK:
                return start + datetime.timedelta(days=7)
            case Recurrence.MONTH:
                return _months_later(start, 1)
            case Recurrence.QUARTER:
                return _months_later(start, 3)
            case Recurrence.YEAR:
                return start.replace(year=start.year + 1)


def _months_later(first_day: datetime.date, months: int) -> datetime.date:
    month = first_day.month - 1 + months
    return first_day.replace(year=first_day.year + month // 12, month=month % 12 + 1)
