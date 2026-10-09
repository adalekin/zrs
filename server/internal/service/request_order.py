"""The orders a list of requests can come in, as one table.

Every rule of the form "what stands above what" lives here and nowhere else: the service
takes the ORDER BY of a list from this table and has no branches by the name of an order.
"""

from sqlalchemy import ColumnElement, select

from internal.entity.enums import RequestSort
from internal.entity.expense_request import ExpenseRequest
from internal.entity.reference_item import ReferenceItem
from internal.service.transitions import FINAL_STATUSES

#: False for a request on its way, true for a finished one: requests on their way stand above.
_finished = ExpenseRequest.status.in_([status.value for status in FINAL_STATUSES])
#: The place the finance director gave the priority of the request, 1 for the most important.
_priority = select(ReferenceItem.position).where(ReferenceItem.id == ExpenseRequest.priority_id).scalar_subquery()
#: The nearest deadline first; a request without a deadline is not more urgent than one with it.
_nearest_deadline = ExpenseRequest.deadline.asc().nulls_last()
#: The request that has waited longer stands above.
_oldest = (ExpenseRequest.created_at.asc(), ExpenseRequest.id.asc())

ORDERS: dict[RequestSort, tuple[ColumnElement, ...]] = {
    RequestSort.CREATED_DESC: (ExpenseRequest.created_at.desc(), ExpenseRequest.id.desc()),
    RequestSort.CREATED: _oldest,
    # Priority and deadline answer "what to deal with first", and a finished request is dealt with.
    RequestSort.PRIORITY: (_finished, _priority.asc(), _nearest_deadline, *_oldest),
    RequestSort.PRIORITY_DESC: (_finished, _priority.desc(), _nearest_deadline, *_oldest),
    RequestSort.DEADLINE: (_finished, _nearest_deadline, _priority.asc(), *_oldest),
    RequestSort.DEADLINE_DESC: (_finished, ExpenseRequest.deadline.desc().nulls_last(), _priority.asc(), *_oldest),
}
