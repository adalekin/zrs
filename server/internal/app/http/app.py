import approck_sqlalchemy_utils.session
from approck_fastapi_utils.exception_handlers import register_exception_handlers
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from internal.config import settings
from internal.controller.http.router import api_router
from internal.exceptions import (
    AttachmentTooLarge,
    FieldInvalid,
    StatusConflict,
    attachment_too_large_handler,
    field_invalid_handler,
    request_validation_handler,
    status_conflict_handler,
)

# ``override_session`` is a (key, dependency) pair once the session factory is initialised.
if not isinstance(approck_sqlalchemy_utils.session.override_session, tuple):
    approck_sqlalchemy_utils.session.init(url=settings.database_url.render_as_string(hide_password=False))


def create_app() -> FastAPI:
    app = FastAPI(
        title="ZRS",
        description="Expense requests: submission, approval and payment tracking",
        version="0.1.0",
    )
    app.include_router(api_router)
    app.dependency_overrides.setdefault(*approck_sqlalchemy_utils.session.override_session)
    register_exception_handlers(app, profile="api")
    app.add_exception_handler(RequestValidationError, request_validation_handler)
    app.add_exception_handler(FieldInvalid, field_invalid_handler)
    app.add_exception_handler(StatusConflict, status_conflict_handler)
    app.add_exception_handler(AttachmentTooLarge, attachment_too_large_handler)
    return app
