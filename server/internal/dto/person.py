from pydantic import BaseModel, ConfigDict

from internal.entity.enums import Role


class PersonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str | None


class MeRead(PersonRead):
    roles: list[Role]
    currencies: list[str]
    attachment_max_bytes: int
