"""Unit tests of the request log middleware on a minimal app (change e1-request-log, task 2.1).

Spec platform/request-log and platform/request-correlation; design RL-03, RL-05, RL-06, RL-07, RL-08. The
middleware writes through an injected writer, so each test reads the lines it produced as dictionaries.
"""

import asyncio
import re
from typing import Any

import anyio
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel

from catalog.api.request_log import RequestLogMiddleware

SERVICE_NAME = "catalog"
FIELDS = {"timestamp", "service", "correlation_id", "method", "route", "status", "duration_seconds", "user_id"}
GATEWAY_ID = "3f2a9c0d4b5e6f708192a3b4c5d6e7f8"
TOKEN_SUB = "5b0c1d2e-3f40-4a5b-8c6d-7e8f9a0b1c2d"
SLOW_ENDPOINT_SECONDS = 0.2
CONCURRENT_REQUESTS = 50


class Purchase(BaseModel):
    quantity: int


def build_app() -> FastAPI:
    """A minimal app with one endpoint per behavior the middleware must log."""
    app = FastAPI()

    @app.get("/ok")
    def ok() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/events/{event_id}/orders/{order_id}")
    def order(event_id: str, order_id: str) -> dict[str, str]:
        return {"event": event_id, "order": order_id}

    @app.get("/slow")
    async def slow() -> dict[str, str]:
        await asyncio.sleep(SLOW_ENDPOINT_SECONDS)
        return {"status": "ok"}

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("unexpected failure")

    @app.post("/purchases")
    def purchase(body: Purchase) -> dict[str, int]:
        return {"quantity": body.quantity}

    # Stands in for an authentication adapter (design RL-06): it stores the accepted sub, or rejects the token.
    @app.get("/admin-only")
    def admin_only(request: Request) -> None:
        sub = request.headers.get("x-test-sub")
        if sub is None:
            raise HTTPException(status_code=401)
        request.state.user_id = sub
        raise HTTPException(status_code=403)

    @app.get("/me")
    def me(request: Request) -> dict[str, str]:
        request.state.user_id = request.headers["x-test-sub"]
        return {"user": request.state.user_id}

    return app


def logged_app(lines: list[dict[str, Any]]) -> FastAPI:
    app = build_app()
    app.add_middleware(RequestLogMiddleware, service_name=SERVICE_NAME, write=lines.append)
    return app


def request_once(path: str, method: str = "GET", **kwargs: Any) -> tuple[httpx.Response, list[dict[str, Any]]]:
    lines: list[dict[str, Any]] = []
    client = TestClient(logged_app(lines), raise_server_exceptions=False)
    response = client.request(method, path, **kwargs)
    return response, lines


def only_line(lines: list[dict[str, Any]]) -> dict[str, Any]:
    assert len(lines) == 1, lines
    return lines[0]


def test_successful_request_writes_one_line_with_the_fixed_fields() -> None:
    """Req: Every backend service writes one log line per request. Scenario: Successful request.

    Also Req: The request log line has a fixed set of fields. Scenario: Fields of a request log line.
    """
    response, lines = request_once("/ok", headers={"X-Correlation-ID": GATEWAY_ID})

    line = only_line(lines)
    assert response.status_code == 200
    assert set(line) == FIELDS
    assert line["service"] == SERVICE_NAME
    assert line["correlation_id"] == GATEWAY_ID
    assert line["method"] == "GET"
    assert line["route"] == "/ok"
    assert line["status"] == 200
    assert line["user_id"] is None
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}\+00:00", line["timestamp"])
    assert isinstance(line["duration_seconds"], float)
    assert line["duration_seconds"] >= 0


def test_route_template_is_logged_instead_of_the_path() -> None:
    """Req: The request log line has a fixed set of fields. Scenario: Route template instead of the requested path."""
    _, lines = request_once("/events/7f3c9a/orders/a12b44")

    line = only_line(lines)
    assert line["route"] == "/events/{event_id}/orders/{order_id}"
    assert "7f3c9a" not in str(line)
    assert "a12b44" not in str(line)


def test_path_that_matches_no_route_logs_a_null_route() -> None:
    """Req: Every backend service writes one log line per request. Scenario: Path that matches no route."""
    response, lines = request_once("/missing/7f3c9a")

    line = only_line(lines)
    assert response.status_code == 404
    assert line["status"] == 404
    assert line["route"] is None


def test_unhandled_error_is_logged_as_500_and_still_answered() -> None:
    """Req: Every backend service writes one log line per request. Scenario: Unhandled error in an endpoint."""
    response, lines = request_once("/boom")

    assert response.status_code == 500
    assert only_line(lines)["status"] == 500


def test_validation_error_is_logged_with_its_status() -> None:
    """Req: Every backend service writes one log line per request. Scenario: Validation error."""
    response, lines = request_once("/purchases", method="POST", json={"quantity": "many"})

    assert response.status_code == 422
    assert only_line(lines)["status"] == 422


def test_rejected_token_logs_401_without_a_user() -> None:
    """Req: Every backend service writes one log line per request. Scenario: Token whose payload cannot be decoded.

    Also Req: The duration covers the whole handling of the request. Scenario: Rejected authentication is timed too.
    """
    response, lines = request_once("/admin-only")

    line = only_line(lines)
    assert response.status_code == 401
    assert line["status"] == 401
    assert line["user_id"] is None
    assert line["duration_seconds"] >= 0


def test_role_failure_logs_403_with_the_token_sub() -> None:
    """Req: Every backend service writes one log line per request. Scenario: Request rejected by the service's
    access rules."""
    response, lines = request_once("/admin-only", headers={"X-Test-Sub": TOKEN_SUB})

    line = only_line(lines)
    assert response.status_code == 403
    assert line["status"] == 403
    assert line["user_id"] == TOKEN_SUB


def test_logged_user_is_the_sub_stored_by_authentication_not_a_forged_header() -> None:
    """Req: The logged user is the token's sub. Scenarios: Authenticated request; Forged identity header."""
    _, lines = request_once("/me", headers={"X-Test-Sub": TOKEN_SUB, "X-User-Id": "someone-else"})

    assert only_line(lines)["user_id"] == TOKEN_SUB


def test_endpoint_without_authentication_logs_no_user_even_with_a_forged_header() -> None:
    """Req: The logged user is the token's sub. Scenario: Public endpoint."""
    _, lines = request_once("/ok", headers={"Authorization": "Bearer abc.def.ghi", "X-User-Id": "someone-else"})

    assert only_line(lines)["user_id"] is None


def test_duration_covers_a_slow_endpoint() -> None:
    """Req: The duration covers the whole handling of the request. Scenario: Slow endpoint."""
    _, lines = request_once("/slow")

    duration = only_line(lines)["duration_seconds"]
    assert SLOW_ENDPOINT_SECONDS <= duration < 2 * SLOW_ENDPOINT_SECONDS


def test_missing_correlation_id_is_logged_as_null() -> None:
    """Req: Services accept only a well-formed correlation id. Scenario: Request without the header."""
    _, lines = request_once("/ok")

    assert only_line(lines)["correlation_id"] is None


def test_malformed_correlation_ids_are_logged_as_null() -> None:
    """Req: Services accept only a well-formed correlation id. Scenario: Malformed header reaching a service."""
    malformed = ['abc"}\\n{"status":200', GATEWAY_ID.upper(), GATEWAY_ID + "0", GATEWAY_ID[:-1]]
    for value in malformed:
        _, lines = request_once("/ok", headers={"X-Correlation-ID": value})

        line = only_line(lines)
        assert line["correlation_id"] is None, value
        assert value not in str(line)


def test_failing_writer_leaves_the_response_unchanged() -> None:
    """Req: Logging never changes the response. Scenarios: Log write fails; Response unchanged by the log."""

    def failing_writer(line: dict[str, Any]) -> None:
        raise OSError("stdout closed")

    app = build_app()
    app.add_middleware(RequestLogMiddleware, service_name=SERVICE_NAME, write=failing_writer)
    logged = TestClient(app).get("/ok")
    plain = TestClient(build_app()).get("/ok")

    assert logged.status_code == plain.status_code == 200
    assert logged.json() == plain.json()
    assert logged.headers["content-type"] == plain.headers["content-type"]


def test_concurrent_requests_write_one_line_each_with_their_own_id_and_user() -> None:
    """Req: Every backend service writes one log line per request. Scenario: Concurrent requests."""
    lines: list[dict[str, Any]] = []
    app = logged_app(lines)
    expected = {f"{index:032x}": f"user-{index}" for index in range(CONCURRENT_REQUESTS)}

    async def send_all() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://catalog") as client:
            await asyncio.gather(
                *(
                    client.get("/me", headers={"X-Correlation-ID": correlation_id, "X-Test-Sub": user})
                    for correlation_id, user in expected.items()
                )
            )

    anyio.run(send_all)

    assert len(lines) == CONCURRENT_REQUESTS
    assert {line["correlation_id"]: line["user_id"] for line in lines} == expected
