from fastapi import APIRouter, Depends, status

from internal.controller.http.deps import get_actor, require_role
from internal.dto.reference_item import ReferenceItemCreate, ReferenceItemRead, ReferenceItemUpdate
from internal.entity.enums import Role
from internal.service.actor import Actor
from internal.service.reference_item import ReferenceItemFilter, ReferenceItemService

router = APIRouter(prefix="/reference-items", tags=["reference lists"])

finance_director_only = require_role(Role.FINANCE_DIRECTOR)


@router.get("", response_model=list[ReferenceItemRead], summary="Values of the reference lists")
async def list_reference_items(
    filter_: ReferenceItemFilter = Depends(),
    _: Actor = Depends(get_actor),
    service: ReferenceItemService = Depends(),
):
    return await service.filter(filter_)


@router.post(
    "",
    response_model=ReferenceItemRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a value to a reference list",
)
async def create_reference_item(
    dto: ReferenceItemCreate,
    _: Actor = Depends(finance_director_only),
    service: ReferenceItemService = Depends(),
):
    return await service.create(dto)


@router.patch(
    "/{item_id}",
    response_model=ReferenceItemRead,
    summary="Rename a value, set its colour, switch it off or on",
)
async def update_reference_item(
    item_id: int,
    dto: ReferenceItemUpdate,
    _: Actor = Depends(finance_director_only),
    service: ReferenceItemService = Depends(),
):
    return await service.update(item_id, dto)
