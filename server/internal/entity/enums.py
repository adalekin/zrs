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
    REASSIGN = "reassign"
    FINISH = "finish"


class Party(StrEnum):
    """What a person is to one particular request."""

    AUTHOR = "author"
    MODERATOR = "moderator"
    #: The second level of approval: a finance director who is neither the author nor the moderator.
    FINANCE_DIRECTOR = "finance_director"
    #: Anyone with the finance director role: disposes of who pays, checks nobody's decision.
    FINANCE_STEWARD = "finance_steward"
    PAYER = "payer"


class ReferenceKind(StrEnum):
    OPERATION_TYPE = "operation_type"
    PAYMENT_FORM = "payment_form"
    PRIORITY = "priority"


class RequestSort(StrEnum):
    """The order of a list of requests. A minus turns the order over."""

    CREATED = "created"
    CREATED_DESC = "-created"
    PRIORITY = "priority"
    PRIORITY_DESC = "-priority"
    DEADLINE = "deadline"
    DEADLINE_DESC = "-deadline"


class ReferenceColor(StrEnum):
    RED = "red"
    ORANGE = "orange"
    YELLOW = "yellow"
    GREEN = "green"
    TEAL = "teal"
    BLUE = "blue"
    VIOLET = "violet"
    PINK = "pink"
