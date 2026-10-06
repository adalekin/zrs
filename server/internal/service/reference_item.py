from dataclasses import dataclass

from approck_services.fastapi import make_service_type
from fastapi import Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import Select

from internal.dto.reference_item import ReferenceItemCreate, ReferenceItemUpdate
from internal.entity.enums import ReferenceKind
from internal.entity.reference_item import ReferenceItem
from internal.exceptions import DuplicateReferenceItem


@dataclass
class ReferenceItemFilter:
    # Query defaults make the dataclass a FastAPI query dependency; the filter base of approck-services reads its fields.
    kind: ReferenceKind | None = Query(None)
    is_active: bool | None = Query(None)


class ReferenceItemService(make_service_type(ReferenceItem, ReferenceItemFilter)):
    async def filter_statement(self, filter_: ReferenceItemFilter) -> tuple[AsyncSession, Select]:
        session, statement = await super().filter_statement(filter_)
        return session, statement.order_by(ReferenceItem.kind, ReferenceItem.name)

    async def has_active(self, kind: ReferenceKind) -> bool:
        statement = (
            select(func.count())
            .select_from(ReferenceItem)
            .where(ReferenceItem.kind == kind.value, ReferenceItem.is_active.is_(True))
        )
        return bool(await self.session.scalar(statement))

    async def find_active(self, kind: ReferenceKind, id_: int) -> ReferenceItem | None:
        return await self._find_one(
            select(ReferenceItem).where(
                ReferenceItem.id == id_, ReferenceItem.kind == kind.value, ReferenceItem.is_active.is_(True)
            )
        )

    async def create(self, dto: ReferenceItemCreate) -> ReferenceItem:
        try:
            return await super().create(dto)
        except IntegrityError as exc:
            await self.session.rollback()
            raise DuplicateReferenceItem(f"The list already has a value named '{dto.name}'") from exc

    async def update(self, id_: int, dto: ReferenceItemUpdate) -> ReferenceItem:
        try:
            return await super().update(id_, dto)
        except IntegrityError as exc:
            await self.session.rollback()
            raise DuplicateReferenceItem(f"The list already has a value named '{dto.name}'") from exc
