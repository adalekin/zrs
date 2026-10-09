from collections.abc import Sequence
from typing import Any

from approck_fastapi_utils.exceptions import Forbidden, NotFound
from approck_services.fastapi import make_service_type
from approck_sqlalchemy_utils.mocks import get_session
from approck_sqlalchemy_utils.transaction import atomic
from fastapi import Depends
from sqlalchemy import ColumnElement, and_, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import lazyload

from internal.config import settings
from internal.dto.expense_request import RequestCreate, RequestUpdate
from internal.dto.request_totals import AmountTotal, RequestTotals
from internal.entity.enums import Action, ReferenceKind, RequestSort, Role, Status
from internal.entity.expense_request import ExpenseRequest, JournalEntry
from internal.exceptions import FieldInvalid, StatusConflict
from internal.service import transitions
from internal.service.actor import Actor
from internal.service.person import PersonService
from internal.service.reference_item import ReferenceItemService
from internal.service.request_order import ORDERS

#: Request fields that reference a list, with the list they must come from and whether a value is required.
REFERENCE_FIELDS: dict[str, tuple[ReferenceKind, bool]] = {
    "operation_type_id": (ReferenceKind.OPERATION_TYPE, True),
    "priority_id": (ReferenceKind.PRIORITY, True),
    "payment_form_id": (ReferenceKind.PAYMENT_FORM, False),
}
#: Fields that may be cleared by an update.
NULLABLE_FIELDS = frozenset({"payment_form_id", "deadline", "payer_id"})


class VisibleTo:
    """Specification: the requests a person may see.

    The author sees their own, a moderator those they are chosen for, a finance director
    and a payer see all. Every read path filters through it, so a request a person may
    not see is indistinguishable from one that does not exist.
    """

    def __init__(self, actor: Actor) -> None:
        self._actor = actor

    def clause(self) -> ColumnElement[bool]:
        if self._actor.has(Role.FINANCE_DIRECTOR) or self._actor.has(Role.PAYER):
            return true()

        conditions = [ExpenseRequest.author_id == self._actor.id]
        if self._actor.has(Role.MODERATOR):
            conditions.append(ExpenseRequest.moderator_id == self._actor.id)
        return or_(*conditions)


class AwaitingActionOf:
    """Specification: the requests that wait for this person's action."""

    def __init__(self, actor: Actor) -> None:
        self._actor = actor

    def clause(self) -> ColumnElement[bool]:
        actor_id = self._actor.id
        conditions = [and_(ExpenseRequest.author_id == actor_id, ExpenseRequest.status == Status.RETURNED.value)]

        if self._actor.has(Role.MODERATOR):
            conditions.append(and_(ExpenseRequest.moderator_id == actor_id, ExpenseRequest.status == Status.NEW.value))
        if self._actor.has(Role.FINANCE_DIRECTOR):
            conditions.append(
                and_(
                    ExpenseRequest.status == Status.ESCALATED.value,
                    ExpenseRequest.author_id != actor_id,
                    ExpenseRequest.moderator_id != actor_id,
                )
            )
        if self._actor.has(Role.PAYER):
            # The same rule as the PAYER party of the transitions: assigned to this person or to nobody.
            conditions.append(
                and_(
                    ExpenseRequest.status == Status.APPROVED.value,
                    or_(ExpenseRequest.payer_id.is_(None), ExpenseRequest.payer_id == actor_id),
                )
            )

        return or_(*conditions)


class ExpenseRequestService(make_service_type(ExpenseRequest)):
    #: Writes flush; the transaction boundary is ``atomic`` in the public methods,
    #: so a status change and its journal entry commit together or not at all.
    autocommit = False

    def __init__(self, session: AsyncSession = Depends(get_session)) -> None:
        super().__init__(session)
        self._person_service = PersonService(session=session)
        self._reference_item_service = ReferenceItemService(session=session)

    # --- reading ---

    async def get(self, actor: Actor, id_: int) -> ExpenseRequest:
        statement = (
            select(ExpenseRequest)
            .where(ExpenseRequest.id == id_, VisibleTo(actor).clause())
            .execution_options(populate_existing=True)
        )
        request = await self._find_one(statement)
        if request is None:
            raise NotFound("Request not found")
        return request

    async def page(
        self,
        actor: Actor,
        *,
        status: Status | None,
        awaiting_me: bool,
        sort: RequestSort,
        page: int,
        size: int,
    ) -> tuple[Sequence[ExpenseRequest], int]:
        conditions = [VisibleTo(actor).clause()]
        if status is not None:
            conditions.append(ExpenseRequest.status == status.value)
        if awaiting_me:
            conditions.append(AwaitingActionOf(actor).clause())

        total = await self.session.scalar(select(func.count()).select_from(ExpenseRequest).where(*conditions))
        statement = (
            select(ExpenseRequest)
            .where(*conditions)
            .options(lazyload(ExpenseRequest.journal), lazyload(ExpenseRequest.attachments))
            .order_by(*ORDERS[sort])
            .limit(size)
            .offset((page - 1) * size)
        )
        return await self._find(statement), total or 0

    async def totals(self, actor: Actor, *, awaiting_me: bool) -> list[RequestTotals]:
        """Counts and sums per status over the same requests ``page`` would list, however many there are."""
        conditions = [VisibleTo(actor).clause()]
        if awaiting_me:
            conditions.append(AwaitingActionOf(actor).clause())

        statement = (
            select(ExpenseRequest.status, ExpenseRequest.currency, func.count(), func.sum(ExpenseRequest.amount))
            .where(*conditions)
            .group_by(ExpenseRequest.status, ExpenseRequest.currency)
            .order_by(ExpenseRequest.currency)
        )
        totals = {status: RequestTotals(status=status, count=0, amounts=[]) for status in Status}
        for status, currency, count, amount in await self.session.execute(statement):
            entry = totals[Status(status)]
            entry.count += count
            entry.amounts.append(AmountTotal(currency=currency, amount=amount))
        return list(totals.values())

    # --- writing ---

    async def create(self, actor: Actor, dto: RequestCreate) -> ExpenseRequest:
        if not actor.has(Role.REQUESTER):
            raise Forbidden("Only a requester may submit a request")

        values = dto.model_dump()
        await self._validate(actor, values, creating=True)

        async with atomic(self.session):
            request = ExpenseRequest(**values, author_id=actor.id, status=Status.NEW.value)
            self.session.add(request)
            await self.session.flush()
            self._record(request, actor, status_changed=True, payer_changed=False, comment=None)

        return await self.get(actor, request.id)

    async def update(self, actor: Actor, id_: int, dto: RequestUpdate) -> ExpenseRequest:
        values = dto.model_dump(exclude_unset=True)

        async with atomic(self.session):
            request = await self._lock(actor, id_)
            if request.author_id != actor.id:
                raise Forbidden("Only the author may change a request")
            if Status(request.status) not in transitions.EDITABLE_STATUSES:
                raise StatusConflict(Status(request.status))

            for field, value in values.items():
                if value is None and field not in NULLABLE_FIELDS:
                    raise FieldInvalid(field, "required", "The field must not be empty")
            await self._validate(actor, values, creating=False)

            for field, value in values.items():
                setattr(request, field, value)

        return await self.get(actor, id_)

    async def act(
        self,
        actor: Actor,
        id_: int,
        action: Action,
        *,
        comment: str | None,
        parameters: dict[str, Any],
    ) -> ExpenseRequest:
        """Apply an action. ``parameters`` are the fields of the body the caller gave, besides the comment."""
        async with atomic(self.session):
            request = await self._lock(actor, id_)
            transition = transitions.resolve(actor, request, action)
            transitions.check_parameters(action, parameters)

            payer_before = request.payer_id
            if "payer_id" in parameters:
                if parameters["payer_id"] is not None:
                    await self._validate_person("payer_id", parameters["payer_id"], Role.PAYER, "not_a_payer")
                request.payer_id = parameters["payer_id"]
            payer_changed = request.payer_id != payer_before
            if "paid_on" in parameters:
                # Whoever marks the payment is the payer of the request from now on.
                request.payer_id = actor.id
                request.paid_on = parameters["paid_on"]

            status_changed = transition.target is not transition.source
            request.status = transition.target.value
            # An action that changed nothing leaves an entry only when it carries a comment.
            if status_changed or payer_changed or comment is not None:
                self._record(
                    request, actor, status_changed=status_changed, payer_changed=payer_changed, comment=comment
                )

        return await self.get(actor, id_)

    async def comment(self, actor: Actor, id_: int, comment: str) -> ExpenseRequest:
        async with atomic(self.session):
            request = await self.get(actor, id_)
            self._record(request, actor, status_changed=False, payer_changed=False, comment=comment)

        return await self.get(actor, id_)

    async def lock_editable(self, actor: Actor, id_: int) -> ExpenseRequest:
        """Lock a request for a change of its attachments. Must run inside the caller's ``atomic``."""
        request = await self._lock(actor, id_)
        if request.author_id != actor.id:
            raise Forbidden("Only the author may change the attachments of a request")
        if Status(request.status) not in transitions.EDITABLE_STATUSES:
            raise StatusConflict(Status(request.status))
        return request

    # --- internals ---

    async def _lock(self, actor: Actor, id_: int) -> ExpenseRequest:
        """Take a row lock on the request and read it afresh.

        A concurrent action waits here, then sees the status the first one left behind.
        """
        await self.session.execute(select(ExpenseRequest.id).where(ExpenseRequest.id == id_).with_for_update())
        return await self.get(actor, id_)

    def _record(
        self, request: ExpenseRequest, actor: Actor, *, status_changed: bool, payer_changed: bool, comment: str | None
    ) -> None:
        self.session.add(
            JournalEntry(
                request_id=request.id,
                person_id=actor.id,
                status=request.status,
                status_changed=status_changed,
                payer_changed=payer_changed,
                payer_id=request.payer_id if payer_changed else None,
                comment=comment,
            )
        )

    async def _validate(self, actor: Actor, values: dict[str, Any], *, creating: bool) -> None:
        """Check the domain rules of the fields present in ``values``."""
        if "currency" in values and values["currency"] not in settings.CURRENCIES:
            raise FieldInvalid("currency", "currency_not_allowed", "The currency is not in the installation's list")

        if "moderator_id" in values:
            await self._validate_moderator(actor, values["moderator_id"])
        if values.get("payer_id") is not None:
            await self._validate_person("payer_id", values["payer_id"], Role.PAYER, "not_a_payer")

        for field, (kind, required) in REFERENCE_FIELDS.items():
            if field not in values and not (creating and required):
                continue
            await self._validate_reference(field, kind, values.get(field), required=required)

    async def _validate_moderator(self, actor: Actor, moderator_id: int) -> None:
        if moderator_id == actor.id:
            raise FieldInvalid("moderator_id", "moderator_is_author", "You cannot choose yourself as the moderator")

        await self._validate_person("moderator_id", moderator_id, Role.MODERATOR, "not_a_moderator")

    async def _validate_person(self, field: str, person_id: int, role: Role, code: str) -> None:
        """The chosen person has signed in and held the role when they last did."""
        person = await self._person_service.find_one(person_id)
        if person is None or role.value not in person.roles:
            raise FieldInvalid(field, code, f"The person does not hold the role '{role.value}'")

    async def _validate_reference(self, field: str, kind: ReferenceKind, value: int | None, *, required: bool) -> None:
        if value is None:
            if not required:
                return
            if not await self._reference_item_service.has_active(kind):
                raise FieldInvalid(
                    field, "reference_list_empty", f"The reference list '{kind.value}' has no active values"
                )
            raise FieldInvalid(field, "required", "The field is required")

        if await self._reference_item_service.find_active(kind, value) is None:
            raise FieldInvalid(
                field,
                "reference_item_inactive",
                f"The value is not an active item of the reference list '{kind.value}'",
            )
