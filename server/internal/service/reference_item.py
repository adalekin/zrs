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
from internal.exceptions import DuplicateReferenceItem, FieldInvalid, ReferenceListUnordered


@dataclass
class ReferenceItemFilter:
    # Query defaults make the dataclass a FastAPI query dependency; the filter base of approck-services reads its fields.
    kind: ReferenceKind | None = Query(None)
    is_active: bool | None = Query(None)


class ReferenceItemService(make_service_type(ReferenceItem, ReferenceItemFilter)):
    async def filter_statement(self, filter_: ReferenceItemFilter) -> tuple[AsyncSession, Select]:
        session, statement = await super().filter_statement(filter_)
        # Priorities come by their place; the lists without an order have no place and come by name.
        return session, statement.order_by(ReferenceItem.kind, ReferenceItem.position, ReferenceItem.name)

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
        item = ReferenceItem(**dto.model_dump())
        try:
            if dto.kind is ReferenceKind.PRIORITY:
                # A new priority takes the place after the last one.
                item.position = len(await self._lock_priorities()) + 1
            return await self._create(item)
        except IntegrityError as exc:
            await self.session.rollback()
            raise DuplicateReferenceItem(f"The list already has a value named '{dto.name}'") from exc

    async def update(self, id_: int, dto: ReferenceItemUpdate) -> ReferenceItem:
        try:
            return await super().update(id_, dto)
        except IntegrityError as exc:
            await self.session.rollback()
            raise DuplicateReferenceItem(f"The list already has a value named '{dto.name}'") from exc

    async def move(self, id_: int, position: int) -> ReferenceItem:
        """Put a priority on another place; the values in between shift by one."""
        item = await self.find_one_or_fail(id_)
        if item.kind != ReferenceKind.PRIORITY.value:
            raise ReferenceListUnordered("Only priorities have an order")

        priorities = await self._lock_priorities()
        if position > len(priorities):
            raise FieldInvalid("position", "position_out_of_range", f"The list has places from 1 to {len(priorities)}")

        others = [priority for priority in priorities if priority.id != id_]
        others.insert(position - 1, item)
        for place, priority in enumerate(others, start=1):
            priority.position = place

        await self._finish()
        await self.session.refresh(item)
        return item

    async def _lock_priorities(self) -> list[ReferenceItem]:
        """The priorities in their order, read under a lock held until the transaction ends.

        Adding a priority and moving one both renumber places. The lock makes them wait for
        each other, so two of them never give one place to two values. It is an advisory lock,
        not a row lock: an empty list has no rows to lock.
        """
        await self.session.execute(
            select(func.pg_advisory_xact_lock(func.hashtext("reference_item.priority.position")))
        )
        statement = (
            select(ReferenceItem)
            .where(ReferenceItem.kind == ReferenceKind.PRIORITY.value)
            .order_by(ReferenceItem.position)
            .execution_options(populate_existing=True)
        )
        return list(await self._find(statement))
