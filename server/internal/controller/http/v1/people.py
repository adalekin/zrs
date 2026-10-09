from approck_sqlalchemy_utils.mocks import get_session
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from internal.config import settings
from internal.controller.http.deps import get_actor
from internal.dto.person import MeRead, NotificationsRead, PaymentDayRead, PersonRead, TelegramLinkCodeRead
from internal.entity.enums import Role
from internal.exceptions import NotificationsOff
from internal.service.actor import Actor
from internal.service.person import PersonService
from internal.service.telegram_link import TelegramLinkService

router = APIRouter(tags=["people"])


@router.get("/me", response_model=MeRead, summary="The signed-in person, their roles and the installation's lists")
async def me(actor: Actor = Depends(get_actor), session: AsyncSession = Depends(get_session)) -> MeRead:
    notifying = settings.NOTIFICATIONS == "telegram"
    return MeRead(
        id=actor.person.id,
        name=actor.person.name,
        email=actor.person.email,
        roles=sorted(actor.roles),
        currencies=settings.CURRENCIES,
        attachment_max_bytes=settings.ATTACHMENT_MAX_BYTES,
        payment_day=PaymentDayRead(
            ends_at=settings.PAYMENT_DAY_ENDS_AT.strftime("%H:%M"), timezone=settings.TIMEZONE.key
        ),
        notifications=NotificationsRead(
            enabled=notifying,
            telegram_linked=notifying and await TelegramLinkService(session).is_linked(actor.id),
        ),
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


@router.post(
    "/telegram-link-codes",
    response_model=TelegramLinkCodeRead,
    status_code=status.HTTP_201_CREATED,
    summary="A one-time link that starts the bot and links the Telegram chat of the current person",
    description="Answers 409 when the installation sends no notifications.",
)
async def create_telegram_link_code(
    actor: Actor = Depends(get_actor), session: AsyncSession = Depends(get_session)
) -> TelegramLinkCodeRead:
    if settings.NOTIFICATIONS != "telegram":
        raise NotificationsOff()
    url, expires_at = await TelegramLinkService(session).issue_code(actor.id)
    return TelegramLinkCodeRead(url=url, expires_at=expires_at)


@router.delete(
    "/telegram-link",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unlink the Telegram chat of the current person",
)
async def remove_telegram_link(actor: Actor = Depends(get_actor), session: AsyncSession = Depends(get_session)) -> None:
    if settings.NOTIFICATIONS != "telegram":
        raise NotificationsOff()
    await TelegramLinkService(session).unlink(actor.id)
