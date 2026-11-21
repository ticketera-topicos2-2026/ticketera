"""Mapping of the catalog's domain and application errors to HTTP answers (change e1-event-catalog).

Rule violations answer 422 in FastAPI's own validation format, so clients and tests read every offending field
from `detail[].loc` whether the schema or the domain found it.
"""

import re

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from catalog.application.exceptions import EventNotFoundError, IdempotencyKeyMismatchError, NotAllowedError
from catalog.domain.event import (
    EventNotEditableError,
    EventNotPublishableError,
    InvalidEventError,
    StaleVersionError,
)

FIELD_PART = re.compile(r"([^.\[\]]+)|\[(\d+)\]")


def _location(prefix: str, field: str) -> list[str | int]:
    """`zones[0].code` becomes [prefix, "zones", 0, "code"], as FastAPI writes locations."""
    parts: list[str | int] = [prefix]
    for name, index in FIELD_PART.findall(field):
        parts.append(int(index) if index else name)
    return parts


def _unprocessable(prefix: str, reasons: dict[str, str]) -> JSONResponse:
    detail = [
        {"loc": _location(prefix, field), "msg": reason, "type": "value_error"}
        for field, reason in reasons.items()
    ]
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": detail})


def _detail(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": message})


def install_error_handlers(app: FastAPI) -> None:
    async def invalid_event(_: Request, error: Exception) -> JSONResponse:
        assert isinstance(error, InvalidEventError)  # noqa: S101 - registered for this type only
        return _unprocessable("body", error.errors)

    async def not_publishable(_: Request, error: Exception) -> JSONResponse:
        assert isinstance(error, EventNotPublishableError)  # noqa: S101 - registered for this type only
        return _unprocessable("event", error.reasons)

    async def key_mismatch(_: Request, __: Exception) -> JSONResponse:
        return _unprocessable("header", {"Idempotency-Key": "was already used with a different request"})

    async def not_found(_: Request, __: Exception) -> JSONResponse:
        # The same answer for a missing event and for another owner's (EC-04).
        return _detail(status.HTTP_404_NOT_FOUND, "Event not found")

    async def not_allowed(_: Request, error: Exception) -> JSONResponse:
        return _detail(status.HTTP_403_FORBIDDEN, str(error))

    async def conflict(_: Request, error: Exception) -> JSONResponse:
        return _detail(status.HTTP_409_CONFLICT, str(error))

    app.add_exception_handler(InvalidEventError, invalid_event)
    app.add_exception_handler(EventNotPublishableError, not_publishable)
    app.add_exception_handler(IdempotencyKeyMismatchError, key_mismatch)
    app.add_exception_handler(EventNotFoundError, not_found)
    app.add_exception_handler(NotAllowedError, not_allowed)
    app.add_exception_handler(StaleVersionError, conflict)
    app.add_exception_handler(EventNotEditableError, conflict)
