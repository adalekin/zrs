from decimal import Decimal

from pydantic import BaseModel, Field

from internal.entity.enums import Status


class AmountTotal(BaseModel):
    currency: str
    amount: Decimal = Field(description="Decimal number as a string, like the amount of a request")


class RequestTotals(BaseModel):
    """How many requests of one status a person sees and how much they add up to, per currency."""

    status: Status
    count: int
    amounts: list[AmountTotal]
