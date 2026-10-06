from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def test_health_answers_ok(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_ready_answers_ok_when_the_schema_is_migrated(client: AsyncClient) -> None:
    response = await client.get("/health/ready")

    assert response.status_code == 200


async def test_ready_refuses_while_the_schema_is_behind_this_build(client: AsyncClient, engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        current = await connection.scalar(text("SELECT version_num FROM alembic_version"))
        await connection.execute(text("UPDATE alembic_version SET version_num = '0000'"))
    try:
        response = await client.get("/health/ready")
    finally:
        async with engine.begin() as connection:
            await connection.execute(text("UPDATE alembic_version SET version_num = :rev"), {"rev": current})

    assert response.status_code == 503


async def test_ready_stays_ok_when_the_schema_is_ahead_of_this_build(client: AsyncClient, engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        current = await connection.scalar(text("SELECT version_num FROM alembic_version"))
        await connection.execute(text("UPDATE alembic_version SET version_num = '9999'"))
    try:
        response = await client.get("/health/ready")
    finally:
        async with engine.begin() as connection:
            await connection.execute(text("UPDATE alembic_version SET version_num = :rev"), {"rev": current})

    assert response.status_code == 200


async def test_openapi_schema_is_served(client: AsyncClient) -> None:
    response = await client.get("/openapi.json")

    assert response.status_code == 200
