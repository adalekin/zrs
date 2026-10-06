"""The request life cycle as one transition table (a table-driven state machine).

Every rule of the form "who may do what from which status" lives here and nowhere else:
the API applies actions through this table and reports available actions from it.
"""

from dataclasses import dataclass
from enum import StrEnum

from approck_fastapi_utils.exceptions import Forbidden

from internal.entity.enums import Action, Role, Status
from internal.entity.expense_request import ExpenseRequest
from internal.exceptions import StatusConflict
from internal.service.actor import Actor


class Party(StrEnum):
    """What a person is to one particular request."""

    AUTHOR = "author"
    MODERATOR = "moderator"
    FINANCE_DIRECTOR = "finance_director"
    PAYER = "payer"


@dataclass(frozen=True)
class Transition:
    action: Action
    source: Status
    target: Status
    party: Party


TRANSITIONS: tuple[Transition, ...] = (
    Transition(Action.RESUBMIT, Status.RETURNED, Status.NEW, Party.AUTHOR),
    Transition(Action.CANCEL, Status.NEW, Status.REJECTED, Party.AUTHOR),
    Transition(Action.CANCEL, Status.RETURNED, Status.REJECTED, Party.AUTHOR),
    Transition(Action.CANCEL, Status.ESCALATED, Status.REJECTED, Party.AUTHOR),
    Transition(Action.CANCEL, Status.APPROVED, Status.REJECTED, Party.AUTHOR),
    Transition(Action.APPROVE, Status.NEW, Status.APPROVED, Party.MODERATOR),
    Transition(Action.ESCALATE, Status.NEW, Status.ESCALATED, Party.MODERATOR),
    Transition(Action.RETURN, Status.NEW, Status.RETURNED, Party.MODERATOR),
    Transition(Action.REJECT, Status.NEW, Status.REJECTED, Party.MODERATOR),
    Transition(Action.APPROVE, Status.ESCALATED, Status.APPROVED, Party.FINANCE_DIRECTOR),
    Transition(Action.RETURN, Status.ESCALATED, Status.RETURNED, Party.FINANCE_DIRECTOR),
    Transition(Action.REJECT, Status.ESCALATED, Status.REJECTED, Party.FINANCE_DIRECTOR),
    Transition(Action.PAY, Status.APPROVED, Status.PAID, Party.PAYER),
)

#: Statuses in which the author may change the fields and the attachments of a request.
EDITABLE_STATUSES: frozenset[Status] = frozenset({Status.NEW, Status.RETURNED})


def parties(actor: Actor, request: ExpenseRequest) -> frozenset[Party]:
    """Everything the actor is to this request.

    A finance director decides only on requests where they are neither the author nor
    the moderator: the second level exists to check someone else's decision.
    """
    is_author = request.author_id == actor.id
    is_moderator = request.moderator_id == actor.id and actor.has(Role.MODERATOR)
    result: set[Party] = set()

    if is_author:
        result.add(Party.AUTHOR)
    if is_moderator:
        result.add(Party.MODERATOR)
    if actor.has(Role.FINANCE_DIRECTOR) and not is_author and request.moderator_id != actor.id:
        result.add(Party.FINANCE_DIRECTOR)
    if actor.has(Role.PAYER):
        result.add(Party.PAYER)

    return frozenset(result)


def resolve(actor: Actor, request: ExpenseRequest, action: Action) -> Transition:
    """Find the transition this actor may apply now.

    Raises ``Forbidden`` when the table has no row giving this action to the actor in
    any status, and ``StatusConflict`` when such a row exists for another status.
    """
    actor_parties = parties(actor, request)
    candidates = [row for row in TRANSITIONS if row.action == action and row.party in actor_parties]

    if not candidates:
        raise Forbidden("The action is not available to you for this request")

    status = Status(request.status)
    for row in candidates:
        if row.source == status:
            return row

    raise StatusConflict(status)


def available_actions(actor: Actor, request: ExpenseRequest) -> list[Action]:
    actor_parties = parties(actor, request)
    status = Status(request.status)
    return [row.action for row in TRANSITIONS if row.source == status and row.party in actor_parties]


def can_edit(actor: Actor, request: ExpenseRequest) -> bool:
    return request.author_id == actor.id and Status(request.status) in EDITABLE_STATUSES
