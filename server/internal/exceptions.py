from approck_fastapi_utils.exceptions import Conflict, CustomException, ServiceUnavailable, UnprocessableEntity
from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from internal.entity.enums import Status


class FieldInvalid(UnprocessableEntity):
    """A request field failed a domain rule. Answered in the shape of a request validation error."""

    def __init__(self, field: str, code: str, message: str) -> None:
        super().__init__(message)
        self.field = field
        #: Stable name of the rule that failed. A client maps it to its own wording; the message is English.
        self.code = code


class StatusConflict(Conflict):
    """The action exists for this person, but not in the current status of the request."""

    def __init__(self, status: Status) -> None:
        super().__init__(f"The action is not available while the request is in status '{status}'")
        self.status = status


class DuplicateReferenceItem(Conflict):
    pass


class AttachmentTooLarge(CustomException):
    status_code = 413

    def __init__(self, limit: int) -> None:
        super().__init__(f"The file exceeds the limit of {limit} bytes")
        self.limit = limit


class IdentityProviderUnavailable(ServiceUnavailable):
    pass


async def request_validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    # Replaces the handler of approck-fastapi-utils 0.2.1, which passes ``exc.errors()`` to
    # the JSON encoder as is and fails on a Decimal in the error context (an amount limit).
    return JSONResponse(
        status_code=422,
        content={"successful": False, "code": "ValidationError", "detail": jsonable_encoder(exc.errors())},
    )


async def field_invalid_handler(_: Request, exc: FieldInvalid) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "successful": False,
            "code": "ValidationError",
            "detail": [{"type": exc.code, "loc": ["body", exc.field], "msg": str(exc)}],
        },
    )


async def status_conflict_handler(_: Request, exc: StatusConflict) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={"successful": False, "code": "StatusConflict", "detail": str(exc), "status": exc.status},
    )


async def attachment_too_large_handler(_: Request, exc: AttachmentTooLarge) -> JSONResponse:
    return JSONResponse(
        status_code=413,
        content={"successful": False, "code": "AttachmentTooLarge", "detail": str(exc), "limit": exc.limit},
    )
