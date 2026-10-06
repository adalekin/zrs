from fastapi import APIRouter, Depends, Query

from internal.config import settings
from internal.controller.http.deps import get_actor
from internal.dto.person import MeRead, PersonRead
from internal.entity.enums import Role
from internal.service.actor import Actor
from internal.service.person import PersonService

router = APIRouter(tags=["people"])


@router.get("/me", response_model=MeRead, summary="The signed-in person, their roles and the installation's lists")
async def me(actor: Actor = Depends(get_actor)) -> MeRead:
    return MeRead(
        id=actor.person.id,
        name=actor.person.name,
        email=actor.person.email,
        roles=sorted(actor.roles),
        currencies=settings.CURRENCIES,
        attachment_max_bytes=settings.ATTACHMENT_MAX_BYTES,
    )


@router.get(
    "/users",
    response_model=list[PersonRead],
    summary="People who have signed in and hold the given role",
    description="Serves the choice of a moderator: only people who have signed in at least once are listed.",
)
async def users(
    role: Role = Query(...),
    _: Actor = Depends(get_actor),
    person_service: PersonService = Depends(),
):
    return await person_service.find_with_role(role)
