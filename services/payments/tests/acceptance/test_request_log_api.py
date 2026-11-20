"""Acceptance tests of the request log on the real payments app (change e1-request-log, task 2.3).

Spec platform/request-log. The app writes its lines to standard output, captured here with capsys; the
smoke test checks the same lines from the running container against tests/platform/request-log.schema.json.
"""

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from payments.api.app import create_app

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


class ReachableDatabaseProbe:
    def is_reachable(self) -> bool:
        return True


def client() -> TestClient:
    return TestClient(create_app(ReachableDatabaseProbe()))


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
        assert line["service"] == "payments"
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
