from approck_fastapi_utils.exceptions import ServiceUnavailable
from approck_sqlalchemy_utils.mocks import get_session
from fastapi import APIRouter, Depends
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from internal.service.schema import Schema

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness probe")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get(
    "/health/ready",
    summary="Readiness probe",
    description=(
        "Ready when the database answers and its schema is at least at the revision this build ships. "
        "A new build therefore receives traffic only after its migrations have run, and an older build "
        "stays ready while a newer one is being rolled out."
    ),
)
async def ready(session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    try:
        migrated = await Schema(session).is_migrated()
    except (DBAPIError, OSError) as exc:
        raise ServiceUnavailable("The database is unavailable or not migrated") from exc

    if not migrated:
        raise ServiceUnavailable("The database schema is behind this build; migrations have not run yet")
    return {"status": "ok"}
