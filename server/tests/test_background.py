import asyncio
import contextlib
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from internal.app.http import background


@contextlib.asynccontextmanager
async def schema_at(engine: AsyncEngine, revision: str) -> AsyncIterator[None]:
    """The database says it is at ``revision`` for the time of the block."""
    async with engine.begin() as connection:
        current = await connection.scalar(text("SELECT version_num FROM alembic_version"))
        await connection.execute(text("UPDATE alembic_version SET version_num = :rev"), {"rev": revision})
    try:
        yield
    finally:
        async with engine.begin() as connection:
            await connection.execute(text("UPDATE alembic_version SET version_num = :rev"), {"rev": current})


async def test_a_background_task_starts_its_work_once_the_migrations_have_run(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(background, "SCHEMA_PAUSE_SECONDS", 0.01)
    passed = asyncio.Event()

    async def step() -> None:
        passed.set()

    task: asyncio.Task[None] | None = None
    try:
        async with schema_at(engine, "0000"):
            task = asyncio.create_task(background.forever(step, pause=0.01))
            await asyncio.sleep(0.2)
            assert not passed.is_set()

        await asyncio.wait_for(passed.wait(), timeout=5)
    finally:
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
