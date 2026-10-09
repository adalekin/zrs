import datetime

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


class NotificationsRead(BaseModel):
    enabled: bool = Field(description="Whether the installation sends notifications")
    telegram_linked: bool = Field(description="Whether the person has linked their Telegram chat")
    telegram_decisions: bool = Field(description="Whether requests may be decided on from the linked Telegram chat")


class TelegramLinkCodeRead(BaseModel):
    url: str = Field(description="The link that starts the bot of the installation for this person")
    expires_at: datetime.datetime


class MeRead(PersonRead):
    roles: list[Role]
    currencies: list[str]
    attachment_max_bytes: int
    payment_day: PaymentDayRead
    notifications: NotificationsRead
