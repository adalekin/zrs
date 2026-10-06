from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from internal.entity.enums import ReferenceKind

ItemName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class ReferenceItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: ReferenceKind
    name: str
    is_active: bool


class ReferenceItemCreate(BaseModel):
    kind: ReferenceKind
    name: ItemName


class ReferenceItemUpdate(BaseModel):
    name: ItemName | None = None
    is_active: bool | None = None
