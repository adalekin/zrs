from functools import lru_cache
from pathlib import Path

from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


class Schema:
    """The schema of the database next to the one this build was written for."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    @lru_cache
    def expected_revision() -> int:
        """The newest migration this build ships. Revision ids are a linear zero-padded sequence."""
        return int(ScriptDirectory(str(MIGRATIONS_DIR)).get_current_head())

    async def is_migrated(self) -> bool:
        """Whether the migrations of this build have run. A newer schema counts: a newer build is rolling out."""
        revision = await self.session.scalar(text("SELECT version_num FROM alembic_version"))
        return revision is not None and int(revision) >= self.expected_revision()
