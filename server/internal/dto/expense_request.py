import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from internal.dto.person import PersonRead
from internal.dto.reference_item import ReferenceItemRead
from internal.entity.enums import Action, Status

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
Amount = Annotated[Decimal, Field(gt=0, max_digits=20, decimal_places=4)]
#: An empty value counts as a missing field; whether the code is allowed is the service's rule.
CurrencyCode = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class RequestCreate(BaseModel):
    # Optional in the schema so that the service can tell "the reference list is empty"
    # from "the field was left out": both are answered as an error on this field.
    operation_type_id: int | None = None
    priority_id: int | None = None
    moderator_id: int
    situation: Text
    solution: Text
    amount: Amount = Field(description="Decimal number as a string, up to four fractional digits")
    currency: CurrencyCode
    payment_period: ShortText
    payment_form_id: int | None = None
    deadline: datetime.date | None = None
    payer_id: int | None = None


class RequestUpdate(BaseModel):
    operation_type_id: int | None = None
    priority_id: int | None = None
    moderator_id: int | None = None
    situation: Text | None = None
    solution: Text | None = None
    amount: Amount | None = None
    currency: CurrencyCode | None = None
    payment_period: ShortText | None = None
    payment_form_id: int | None = None
    deadline: datetime.date | None = None
    payer_id: int | None = None


class ActionRequest(BaseModel):
    comment: Text | None = None
    paid_on: datetime.date | None = Field(default=None, description="Payment date, required by the pay action")
    payer_id: int | None = Field(
        default=None,
        description=(
            "The payer of the request. The approve action may name one; the reassign action must carry the "
            "field, and a null there leaves the request to any payer"
        ),
    )


class CommentCreate(BaseModel):
    comment: Text


class JournalEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    person: PersonRead
    status: Status
    status_changed: bool
    payer_changed: bool
    payer: PersonRead | None
    comment: str | None
    created_at: datetime.datetime


class AttachmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    content_type: str
    size: int
    created_at: datetime.datetime


class RequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: Status
    author: PersonRead
    moderator: PersonRead
    payer: PersonRead | None
    operation_type: ReferenceItemRead
    payment_form: ReferenceItemRead | None
    priority: ReferenceItemRead
    situation: str
    solution: str
    amount: Decimal
    currency: str
    payment_period: str
    deadline: datetime.date | None
    paid_on: datetime.date | None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class RequestDetail(RequestRead):
    attachments: list[AttachmentRead]
    journal: list[JournalEntryRead]
    actions: list[Action] = Field(description="Actions the current person may apply right now")
    can_edit: bool = Field(description="Whether the current person may change fields and attachments right now")


class RequestPage(BaseModel):
    items: list[RequestRead]
    total: int
    page: int
    size: int
