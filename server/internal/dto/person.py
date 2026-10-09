from pydantic import BaseModel, ConfigDict, Field

from internal.entity.enums import Role


class PersonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str | None


class PaymentDayRead(BaseModel):
    ends_at: str = Field(description="The time of day, HH:MM, after which a payment is not made the same day")
    timezone: str = Field(description="The IANA time zone that time is in")


class MeRead(PersonRead):
    roles: list[Role]
    currencies: list[str]
    attachment_max_bytes: int
    payment_day: PaymentDayRead
