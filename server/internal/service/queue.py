import datetime

from sqlalchemy import TIMESTAMP, ColumnElement, Date, and_, cast, false, func, or_

from internal.entity.enums import Role, Status
from internal.entity.expense_request import ExpenseRequest
from internal.entity.person import Person
from internal.service.actor import Actor


class Queue:
    """Specification: whom a request waits for on a given day, read in both directions.

    The requests that wait for a person fill their list, their counter and their board;
    the people a request waits for are told about it. Both readings are one rule, and a
    test holds them together. The day matters to a payer alone: a recurring request paid
    for the current period waits for nobody until the next one starts.
    """

    def __init__(self, today: datetime.date) -> None:
        self._today = today

    def requests_awaiting(self, actor: Actor) -> ColumnElement[bool]:
        """The requests that wait for this person's action."""
        actor_id = actor.id
        conditions = [and_(ExpenseRequest.author_id == actor_id, ExpenseRequest.status == Status.RETURNED.value)]

        if actor.has(Role.MODERATOR):
            conditions.append(and_(ExpenseRequest.moderator_id == actor_id, ExpenseRequest.status == Status.NEW.value))
        if actor.has(Role.FINANCE_DIRECTOR):
            conditions.append(
                and_(
                    ExpenseRequest.status == Status.ESCALATED.value,
                    ExpenseRequest.author_id != actor_id,
                    ExpenseRequest.moderator_id != actor_id,
                )
            )
        if actor.has(Role.PAYER):
            # The same rule as the PAYER party of the transitions: assigned to this person or to nobody.
            conditions.append(
                and_(
                    ExpenseRequest.status == Status.APPROVED.value,
                    or_(ExpenseRequest.payer_id.is_(None), ExpenseRequest.payer_id == actor_id),
                    # The same rule as ``ExpenseRequest.back_in_queue_on``, said to the database.
                    or_(
                        ExpenseRequest.recurrence.is_(None),
                        ExpenseRequest.paid_on.is_(None),
                        ExpenseRequest.paid_on < self.period_start(),
                    ),
                )
            )

        return or_(*conditions)

    def people_awaited_by(self, request: ExpenseRequest) -> ColumnElement[bool]:
        """The people this request waits for, by the roles their latest sign-in gave them."""
        match Status(request.status):
            case Status.RETURNED:
                return Person.id == request.author_id
            case Status.NEW:
                return and_(Person.id == request.moderator_id, self._holds(Role.MODERATOR))
            case Status.ESCALATED:
                return and_(
                    self._holds(Role.FINANCE_DIRECTOR),
                    Person.id != request.author_id,
                    Person.id != request.moderator_id,
                )
            case Status.APPROVED:
                if request.back_in_queue_on(self._today) is not None:
                    return false()
                payers = self._holds(Role.PAYER)
                return payers if request.payer_id is None else and_(payers, Person.id == request.payer_id)
            case Status.PAID | Status.REJECTED:
                return false()

    def period_start(self) -> ColumnElement[datetime.date]:
        """The first day of the current period of a request, by its own recurrence."""
        return cast(func.date_trunc(ExpenseRequest.recurrence, cast(self._today, TIMESTAMP)), Date)

    @staticmethod
    def _holds(role: Role) -> ColumnElement[bool]:
        return Person.roles.contains([role.value])
