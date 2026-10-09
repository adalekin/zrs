from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from internal.entity.enums import ReferenceColor, ReferenceKind

ItemName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class ReferenceItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: ReferenceKind
    name: str
    is_active: bool
    color: ReferenceColor | None
    position: int | None = Field(
        description="Place of a priority in its list, from 1; null in the lists without an order"
    )


class ReferenceItemCreate(BaseModel):
    kind: ReferenceKind
    name: ItemName


class ReferenceItemUpdate(BaseModel):
    name: ItemName | None = None
    is_active: bool | None = None
    # A field left out of the body keeps its value; an explicit null takes the colour away.
    color: ReferenceColor | None = None


class ReferenceItemPlace(BaseModel):
    position: int = Field(ge=1, description="The place to put the value on, from 1")
