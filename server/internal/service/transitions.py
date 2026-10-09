"""The request life cycle as one transition table (a table-driven state machine).

Every rule of the form "who may do what from which status" lives here and nowhere else:
the API applies actions through this table and reports available actions from it.
"""

from dataclasses import dataclass
from typing import Any

from approck_fastapi_utils.exceptions import Forbidden

from internal.entity.enums import Action, Party, Role, Status
from internal.entity.expense_request import ExpenseRequest
from internal.exceptions import FieldInvalid, StatusConflict
from internal.service.actor import Actor


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
    Transition(Action.REASSIGN, Status.APPROVED, Status.APPROVED, Party.FINANCE_STEWARD),
)


@dataclass(frozen=True)
class Parameter:
    """A field of the request body that an action takes."""

    #: The body must carry the field.
    required: bool = False
    #: The field may be null: the action then clears what the field sets.
    nullable: bool = False


#: The parameters each action takes besides the comment. A field given to an action that does
#: not list it is refused: a payment date belongs to paying, a payer to approving and reassigning.
ACTION_PARAMETERS: dict[Action, dict[str, Parameter]] = {
    Action.PAY: {"paid_on": Parameter(required=True)},
    Action.APPROVE: {"payer_id": Parameter()},
    Action.REASSIGN: {"payer_id": Parameter(required=True, nullable=True)},
}

#: Statuses no transition leaves: the request is finished.
FINAL_STATUSES: frozenset[Status] = frozenset(Status) - {transition.source for transition in TRANSITIONS}

#: Statuses in which the author may change the fields and the attachments of a request.
EDITABLE_STATUSES: frozenset[Status] = frozenset({Status.NEW, Status.RETURNED})


def parties(actor: Actor, request: ExpenseRequest) -> frozenset[Party]:
    """Everything the actor is to this request.

    A finance director decides only on requests where they are neither the author nor
    the moderator: the second level exists to check someone else's decision. A payer is
    a party to the requests assigned to them and to the ones assigned to nobody.
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
    if actor.has(Role.FINANCE_DIRECTOR):
        result.add(Party.FINANCE_STEWARD)
    if actor.has(Role.PAYER) and request.payer_id in (None, actor.id):
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


def check_parameters(action: Action, given: dict[str, Any]) -> None:
    """Refuse a body that carries a field the action does not take or lacks one it needs."""
    accepted = ACTION_PARAMETERS.get(action, {})

    for name in given:
        if name not in accepted:
            raise FieldInvalid(name, "not_accepted", f"The action '{action}' does not take this field")
    for name, parameter in accepted.items():
        if name not in given:
            if parameter.required:
                raise FieldInvalid(name, "required", "The field is required")
        elif given[name] is None and not parameter.nullable:
            raise FieldInvalid(name, "required", "The field must not be empty")


def available_actions(actor: Actor, request: ExpenseRequest) -> list[Action]:
    actor_parties = parties(actor, request)
    status = Status(request.status)
    return [row.action for row in TRANSITIONS if row.source == status and row.party in actor_parties]


def can_edit(actor: Actor, request: ExpenseRequest) -> bool:
    return request.author_id == actor.id and Status(request.status) in EDITABLE_STATUSES
