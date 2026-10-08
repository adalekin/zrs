from enum import StrEnum


class Role(StrEnum):
    REQUESTER = "requester"
    MODERATOR = "moderator"
    FINANCE_DIRECTOR = "finance_director"
    PAYER = "payer"


class Status(StrEnum):
    NEW = "new"
    RETURNED = "returned"
    ESCALATED = "escalated"
    APPROVED = "approved"
    PAID = "paid"
    REJECTED = "rejected"


class Action(StrEnum):
    APPROVE = "approve"
    ESCALATE = "escalate"
    RETURN = "return"
    REJECT = "reject"
    RESUBMIT = "resubmit"
    CANCEL = "cancel"
    PAY = "pay"


class ReferenceKind(StrEnum):
    OPERATION_TYPE = "operation_type"
    PAYMENT_FORM = "payment_form"
    PRIORITY = "priority"


class ReferenceColor(StrEnum):
    RED = "red"
    ORANGE = "orange"
    YELLOW = "yellow"
    GREEN = "green"
    TEAL = "teal"
    BLUE = "blue"
    VIOLET = "violet"
    PINK = "pink"
