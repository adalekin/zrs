import datetime

from fastapi import APIRouter, Depends, Query

from internal.controller.http.deps import get_actor, get_today
from internal.dto.request_totals import RequestTotals
from internal.service.actor import Actor
from internal.service.expense_request import ExpenseRequestService

router = APIRouter(prefix="/request-totals", tags=["requests"])


@router.get(
    "",
    response_model=list[RequestTotals],
    summary="Counts and sums of the requests visible to the current person, one entry per status",
)
async def list_request_totals(
    awaiting_me: bool = Query(False, description="Only the requests that wait for the current person's action"),
    actor: Actor = Depends(get_actor),
    today: datetime.date = Depends(get_today),
    service: ExpenseRequestService = Depends(),
) -> list[RequestTotals]:
    return await service.totals(actor, awaiting_me=awaiting_me, today=today)
