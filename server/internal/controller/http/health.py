from functools import lru_cache
from pathlib import Path

from alembic.script import ScriptDirectory
from approck_fastapi_utils.exceptions import ServiceUnavailable
from approck_sqlalchemy_utils.mocks import get_session
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["health"])

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "migrations"


@lru_cache
def expected_revision() -> int:
    """The newest migration this build ships. Revision ids are a linear zero-padded sequence."""
    return int(ScriptDirectory(str(MIGRATIONS_DIR)).get_current_head())


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
        revision = await session.scalar(text("SELECT version_num FROM alembic_version"))
    except (DBAPIError, OSError) as exc:
        raise ServiceUnavailable("The database is unavailable or not migrated") from exc

    if revision is None or int(revision) < expected_revision():
        raise ServiceUnavailable("The database schema is behind this build; migrations have not run yet")
    return {"status": "ok"}
