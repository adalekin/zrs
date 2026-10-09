from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Response, UploadFile, status

from internal.controller.http.deps import get_actor, get_storage
from internal.dto.expense_request import (
    ActionRequest,
    AttachmentRead,
    CommentCreate,
    JournalEntryRead,
    RequestCreate,
    RequestDetail,
    RequestPage,
    RequestRead,
    RequestUpdate,
)
from internal.entity.enums import Action, RequestSort, Status
from internal.entity.expense_request import ExpenseRequest
from internal.service import transitions
from internal.service.actor import Actor
from internal.service.attachment import AttachmentService
from internal.service.expense_request import ExpenseRequestService
from internal.service.storage import AttachmentStorage

router = APIRouter(prefix="/requests", tags=["requests"])


def _detail(actor: Actor, request: ExpenseRequest) -> RequestDetail:
    # Not a 1:1 projection of the entity: the actions and the edit flag depend on who asks.
    return RequestDetail(
        **RequestRead.model_validate(request).model_dump(),
        attachments=[AttachmentRead.model_validate(attachment) for attachment in request.attachments],
        journal=[JournalEntryRead.model_validate(entry) for entry in request.journal],
        actions=transitions.available_actions(actor, request),
        can_edit=transitions.can_edit(actor, request),
    )


@router.get("", response_model=RequestPage, summary="Requests visible to the current person")
async def list_requests(
    status_: Status | None = Query(None, alias="status"),
    awaiting_me: bool = Query(False, description="Only the requests that wait for the current person's action"),
    sort: RequestSort = Query(
        RequestSort.CREATED_DESC,
        description=(
            "The order of the list; a minus turns it over. By priority and by deadline the finished requests "
            "stand below the rest, and a request without a deadline stands below the ones that have it"
        ),
    ),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    actor: Actor = Depends(get_actor),
    service: ExpenseRequestService = Depends(),
) -> RequestPage:
    items, total = await service.page(actor, status=status_, awaiting_me=awaiting_me, sort=sort, page=page, size=size)
    return RequestPage(
        items=[RequestRead.model_validate(item) for item in items],
        total=total,
        page=page,
        size=size,
    )


@router.post("", response_model=RequestDetail, status_code=status.HTTP_201_CREATED, summary="Submit a request")
async def create_request(
    dto: RequestCreate,
    actor: Actor = Depends(get_actor),
    service: ExpenseRequestService = Depends(),
) -> RequestDetail:
    return _detail(actor, await service.create(actor, dto))


@router.get("/{request_id}", response_model=RequestDetail, summary="A request with its journal and available actions")
async def get_request(
    request_id: int,
    actor: Actor = Depends(get_actor),
    service: ExpenseRequestService = Depends(),
) -> RequestDetail:
    return _detail(actor, await service.get(actor, request_id))


@router.patch(
    "/{request_id}",
    response_model=RequestDetail,
    summary="Change the fields of a request",
    description="Available to the author while the request is new or returned.",
)
async def update_request(
    request_id: int,
    dto: RequestUpdate,
    actor: Actor = Depends(get_actor),
    service: ExpenseRequestService = Depends(),
) -> RequestDetail:
    return _detail(actor, await service.update(actor, request_id, dto))


@router.post(
    "/{request_id}/comments",
    response_model=RequestDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Add a comment without changing the status",
)
async def add_comment(
    request_id: int,
    dto: CommentCreate,
    actor: Actor = Depends(get_actor),
    service: ExpenseRequestService = Depends(),
) -> RequestDetail:
    return _detail(actor, await service.comment(actor, request_id, dto.comment))


@router.post(
    "/{request_id}/attachments",
    response_model=AttachmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Attach a payment document",
)
async def add_attachment(
    request_id: int,
    file: UploadFile,
    actor: Actor = Depends(get_actor),
    service: AttachmentService = Depends(),
    storage: AttachmentStorage = Depends(get_storage),
):
    return await service.add(actor, request_id, file, storage)


@router.get("/{request_id}/attachments/{attachment_id}", summary="Download a payment document")
async def download_attachment(
    request_id: int,
    attachment_id: int,
    actor: Actor = Depends(get_actor),
    service: AttachmentService = Depends(),
    storage: AttachmentStorage = Depends(get_storage),
) -> Response:
    attachment, body = await service.read(actor, request_id, attachment_id, storage)
    return Response(
        content=body,
        media_type=attachment.content_type,
        headers={
            # Always a download, never rendered in place: the content type comes from whoever uploaded the file.
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(attachment.filename)}",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.delete(
    "/{request_id}/attachments/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a payment document",
)
async def remove_attachment(
    request_id: int,
    attachment_id: int,
    actor: Actor = Depends(get_actor),
    service: AttachmentService = Depends(),
    storage: AttachmentStorage = Depends(get_storage),
) -> None:
    await service.remove(actor, request_id, attachment_id, storage)


@router.post(
    "/{request_id}/{action}",
    response_model=RequestDetail,
    summary="Apply an action to a request",
    description=(
        "Moves the request along its life cycle. Answers 403 when the action is never available to the "
        "current person for this request, and 409 with the current status when it is available in another status."
    ),
)
async def act_on_request(
    request_id: int,
    action: Action,
    dto: ActionRequest | None = None,
    actor: Actor = Depends(get_actor),
    service: ExpenseRequestService = Depends(),
) -> RequestDetail:
    body = dto or ActionRequest()
    request = await service.act(actor, request_id, action, comment=body.comment, paid_on=body.paid_on)
    return _detail(actor, request)
