"""Acceptance tests of the request log on the real sales app (change e1-request-log, task 3.1).

Spec platform/request-log. The app writes its lines to standard output, captured here with capsys; the
smoke test checks the same lines from the running container against tests/platform/request-log.schema.json.
"""

import base64
import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from sales.api.app import create_app
from sales.application.health import DatabaseProbe
from tests.unit.fake_uow import InMemoryUnitOfWork
from tests.unit.test_api_endpoints import (
    InMemoryIdempotencyStore,
    InMemoryInventoryRepo,
    InMemoryOrderRepo,
)

FIELDS = {
    "timestamp",
    "service",
    "correlation_id",
    "method",
    "route",
    "status",
    "duration_seconds",
    "user_id",
}
TOKEN = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ0b2tlbi1tYXJrZXIifQ.c2lnbmF0dXJlLW1hcmtlcg"
COOKIE_VALUE = "cookie-marker-7d1e"
QUERY_TOKEN = "query-token-marker-4b2a"
PERSONAL_NAME = "Ana Marker Perez"
PERSONAL_EMAIL = "ana.marker@example.com"
CLIENT_SUB = "client-sub-4f8a9c0d"


class ReachableDatabaseProbe(DatabaseProbe):
    def is_reachable(self) -> bool:
        return True


def _make_jwt(sub: str, roles: list[str]) -> str:
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none"}).encode()).decode().rstrip("=")
    payload = (
        base64.urlsafe_b64encode(
            json.dumps({"sub": sub, "realm_access": {"roles": roles}}).encode()
        )
        .decode()
        .rstrip("=")
    )
    return f"{header}.{payload}."


def client() -> TestClient:
    inv_repo = InMemoryInventoryRepo()
    order_repo = InMemoryOrderRepo()
    idem_store = InMemoryIdempotencyStore()
    return TestClient(
        create_app(
            database_probe=ReachableDatabaseProbe(),
            uow_factory=lambda: InMemoryUnitOfWork(inv_repo, order_repo, idem_store),
        )
    )


def logged_lines(captured: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in captured.splitlines() if line.strip()]


def test_each_request_writes_one_line_with_the_fixed_fields(capsys: pytest.CaptureFixture[str]) -> None:
    """Req: Every backend service writes one log line per request. Scenario: Successful request.

    Also Req: The request log line has a fixed set of fields. Scenario: Fields of a request log line.
    """
    test_client = client()
    test_client.get("/health")
    test_client.head("/health")

    lines = logged_lines(capsys.readouterr().out)
    assert [(line["method"], line["route"], line["status"]) for line in lines] == [
        ("GET", "/health", 200),
        ("HEAD", "/health", 200),
    ]
    for line in lines:
        assert set(line) == FIELDS
        assert line["service"] == "sales"
        assert line["user_id"] is None


def test_tokens_cookies_and_query_strings_are_never_logged(capsys: pytest.CaptureFixture[str]) -> None:
    """Req: The request log never contains sensitive data.

    Scenarios: Request with a token; Token in the query string; Cookie header.
    """
    client().get(
        f"/health?access_token={QUERY_TOKEN}",
        headers={"Authorization": f"Bearer {TOKEN}", "Cookie": f"session={COOKIE_VALUE}"},
    )

    output = capsys.readouterr().out
    assert len(logged_lines(output)) == 1
    for secret in (TOKEN, *TOKEN.split("."), COOKIE_VALUE, QUERY_TOKEN, "access_token"):
        assert secret not in output


def test_request_bodies_are_never_logged(capsys: pytest.CaptureFixture[str]) -> None:
    """Req: The request log never contains sensitive data. Scenario: Body with personal data."""
    response = client().post("/health", json={"name": PERSONAL_NAME, "email": PERSONAL_EMAIL})

    output = capsys.readouterr().out
    assert response.status_code == 405
    assert [line["status"] for line in logged_lines(output)] == [405]
    assert PERSONAL_NAME not in output
    assert PERSONAL_EMAIL not in output


def test_authenticated_client_request_logs_token_sub_not_forged_header(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Req: The logged user is the token's sub. Scenarios: Authenticated request; Forged identity header."""
    token = _make_jwt(CLIENT_SUB, ["CLIENT"])
    response = client().get(
        "/events/ev-log-1/seats",
        headers={"Authorization": f"Bearer {token}", "X-User-Id": "forged-user"},
    )

    lines = logged_lines(capsys.readouterr().out)
    assert response.status_code == 200
    assert len(lines) == 1
    assert lines[0]["route"] == "/events/{event_id}/seats"
    assert lines[0]["status"] == 200
    assert lines[0]["user_id"] == CLIENT_SUB


def test_client_calling_admin_endpoint_logs_403_with_token_sub(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Req: Every backend service writes one log line per request.

    Scenario: Request rejected by the service's access rules.
    Also Req: The logged user is the token's sub. Scenario: Authenticated request.
    """
    token = _make_jwt(CLIENT_SUB, ["CLIENT"])
    response = client().post(
        "/events/ev-log-1/inventory",
        headers={"Authorization": f"Bearer {token}"},
        json={"seats": [{"seat_id": "A1", "category": "VIP", "price_centavos": 10000}]},
    )

    lines = logged_lines(capsys.readouterr().out)
    assert response.status_code == 403
    assert len(lines) == 1
    assert lines[0]["route"] == "/events/{event_id}/inventory"
    assert lines[0]["status"] == 403
    assert lines[0]["user_id"] == CLIENT_SUB


def test_unauthenticated_and_malformed_token_requests_log_401_with_null_user(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Req: The logged user is the token's sub. Scenarios: Public endpoint; Rejected token."""
    test_client = client()
    r1 = test_client.get("/events/ev-log-1/seats")
    r2 = test_client.get("/events/ev-log-1/seats", headers={"Authorization": "Bearer not-a-jwt"})

    lines = logged_lines(capsys.readouterr().out)
    assert r1.status_code == 401
    assert r2.status_code == 401
    assert len(lines) == 2
    assert all(line["status"] == 401 and line["user_id"] is None for line in lines)
