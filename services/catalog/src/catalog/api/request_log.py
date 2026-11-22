"""Request log middleware: one JSON line per HTTP request on standard output.

Change e1-request-log (spec platform/request-log, platform/request-correlation; design RL-03 to RL-10).
It is an inbound adapter concern, so it lives in the api layer; the domain and application layers do not
know it exists.

The line is built from scratch with a fixed set of fields (allow-list, RL-08): no header, query string or
body ever reaches it. The user is the `sub` that the authentication adapter stores in
`request.state.user_id` once it has accepted the token (RL-06); this module never reads the token.
"""

import json
import re
import sys
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

CORRELATION_HEADER = b"x-correlation-id"
# The gateway's $request_id: 32 lowercase hexadecimal characters (RL-01, RL-03).
CORRELATION_ID_PATTERN = re.compile(r"[0-9a-f]{32}")
# Status logged when the app raises before it starts a response; Starlette's error middleware answers 500.
UNANSWERED_STATUS = 500

LogLine = dict[str, Any]
LogWriter = Callable[[LogLine], None]

_stdout_lock = threading.Lock()


def write_to_stdout(line: LogLine) -> None:
    """Writes one line as compact JSON; the lock keeps concurrent lines whole (RL-10)."""
    text = json.dumps(line, separators=(",", ":"), ensure_ascii=True)
    with _stdout_lock:
        sys.stdout.write(text + "\n")
        sys.stdout.flush()


class RequestLogMiddleware:
    """Pure ASGI middleware (RL-05): times the whole request and writes its line after the response."""

    def __init__(self, app: ASGIApp, service_name: str, write: LogWriter = write_to_stdout) -> None:
        self.app = app
        self.service_name = service_name
        self.write = write
        self._write_failure_reported = False

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started = time.perf_counter()
        status = UNANSWERED_STATUS

        async def send_and_capture_status(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_and_capture_status)
        finally:
            self._log(scope, status, time.perf_counter() - started)

    def _log(self, scope: Scope, status: int, duration_seconds: float) -> None:
        try:
            self.write(build_line(self.service_name, scope, status, duration_seconds))
        except Exception:  # noqa: BLE001 - logging must never change the response (spec: Log write fails)
            if not self._write_failure_reported:
                self._write_failure_reported = True
                print(
                    "request log: a line could not be written; later failures are not reported",
                    file=sys.stderr,
                )


def build_line(service_name: str, scope: Scope, status: int, duration_seconds: float) -> LogLine:
    return {
        "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds"),
        "service": service_name,
        "correlation_id": correlation_id(scope),
        "method": scope["method"],
        "route": route_template(scope),
        "status": status,
        "duration_seconds": round(duration_seconds, 3),
        "user_id": user_id(scope),
    }


def correlation_id(scope: Scope) -> str | None:
    """The gateway's correlation id, or None when it is missing, repeated or malformed (RL-03)."""
    values = [value for name, value in scope["headers"] if name == CORRELATION_HEADER]
    if len(values) != 1:
        return None
    value = values[0].decode("latin-1")
    return value if CORRELATION_ID_PATTERN.fullmatch(value) else None


def route_template(scope: Scope) -> str | None:
    """The template of the matched route, such as /events/{event_id}/orders, or None (RL-07)."""
    path = getattr(scope.get("route"), "path", None)
    return path if isinstance(path, str) else None


def user_id(scope: Scope) -> str | None:
    """The sub stored by the authentication adapter in request.state.user_id (RL-06)."""
    state = scope.get("state")
    value = state.get("user_id") if isinstance(state, dict) else None
    return value if isinstance(value, str) else None
