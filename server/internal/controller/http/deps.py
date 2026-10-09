import datetime
from functools import lru_cache

from approck_fastapi_utils.exceptions import Forbidden, Unauthorized
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from internal.config import settings
from internal.entity.enums import Role
from internal.service.actor import Actor
from internal.service.claims import ClaimsMapper
from internal.service.oidc import OIDCVerifier
from internal.service.person import PersonService
from internal.service.storage import AttachmentStorage

bearer = HTTPBearer(auto_error=False)


@lru_cache
def get_verifier() -> OIDCVerifier:
    return OIDCVerifier(issuer=settings.OIDC_ISSUER, audience=settings.OIDC_AUDIENCE)


@lru_cache
def get_claims_mapper() -> ClaimsMapper:
    return ClaimsMapper(
        roles_claim=settings.OIDC_ROLES_CLAIM,
        role_values={
            Role.REQUESTER: settings.ROLE_REQUESTER,
            Role.MODERATOR: settings.ROLE_MODERATOR,
            Role.FINANCE_DIRECTOR: settings.ROLE_FINANCE_DIRECTOR,
            Role.PAYER: settings.ROLE_PAYER,
        },
    )


@lru_cache
def get_storage() -> AttachmentStorage:
    return AttachmentStorage(
        aws_access_key_id=settings.S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        region_name=settings.S3_REGION,
        bucket=settings.S3_BUCKET,
        endpoint_url=settings.S3_ENDPOINT_URL,
    )


def get_today() -> datetime.date:
    """The calendar day on the clock of the installation: periods of payment are counted by it."""
    return datetime.datetime.now(settings.TIMEZONE).date()


async def get_actor(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    verifier: OIDCVerifier = Depends(get_verifier),
    claims_mapper: ClaimsMapper = Depends(get_claims_mapper),
    person_service: PersonService = Depends(),
) -> Actor:
    if credentials is None:
        raise Unauthorized("Not authenticated")

    payload = await verifier.verify(credentials.credentials)
    roles = claims_mapper.roles(payload)
    person = await person_service.sync(payload, roles, credentials.credentials, verifier)

    if person is None or not roles:
        raise Forbidden("No role grants you access to this service")

    return Actor(person=person, roles=roles)


def require_role(role: Role):
    def dependency(actor: Actor = Depends(get_actor)) -> Actor:
        if not actor.has(role):
            raise Forbidden("Your role does not allow this action")
        return actor

    return dependency
