"""API tests of GET /health with a fake database probe (spec platform/service-health)."""

import time

import pytest
from fastapi.testclient import TestClient

from catalog.api.app import create_app
from catalog.application.health import DatabaseProbe

HEALTHY_BODY = {"status": "ok", "service": "catalog", "database": "ok"}
UNAVAILABLE_BODY = {"status": "unavailable", "service": "catalog", "database": "unavailable"}


class FakeDatabaseProbe:
    """Test double of the database probe port; its answer can change between requests."""

    def __init__(self, reachable: bool) -> None:
        self.reachable = reachable

    def is_reachable(self) -> bool:
        return self.reachable


class FailingDatabaseProbe:
    """Probe that raises, as a broken adapter would, with internal details in the message."""

    def is_reachable(self) -> bool:
        raise RuntimeError("connection to server at 'database' (172.18.0.2) failed: password=secret")


def client_with(probe: DatabaseProbe) -> TestClient:
    return TestClient(create_app(probe))


def test_healthy_service_answers_200_with_exactly_three_fields_within_one_second() -> None:
    """Req: The health endpoint reports a healthy service. Scenario: Healthy catalog service.

    Also Req: The health response reveals no internal details. Scenario: Healthy response content.
    """
    client = client_with(FakeDatabaseProbe(reachable=True))

    started = time.monotonic()
    response = client.get("/health")
    elapsed = time.monotonic() - started

    assert response.status_code == 200
    assert response.json() == HEALTHY_BODY
    assert elapsed < 1


def test_unreachable_database_answers_503_with_unavailable() -> None:
    """Req: The health endpoint reports an unreachable database. Scenario: Database stopped.

    Also Req: The health response reveals no internal details. Scenario: Response while the database is
    unavailable.
    """
    client = client_with(FakeDatabaseProbe(reachable=False))

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == UNAVAILABLE_BODY


def test_failing_probe_answers_503_without_internal_details() -> None:
    """Req: The health response reveals no internal details. Scenario: Response while the database is
    unavailable (the error message of the database adapter never reaches the body).
    """
    client = client_with(FailingDatabaseProbe())

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == UNAVAILABLE_BODY
    assert "secret" not in response.text
    assert "172.18.0.2" not in response.text


def test_service_answers_200_again_after_the_database_recovers() -> None:
    """Req: The health endpoint reports an unreachable database. Scenario: Database available again
    (without restarting the service).
    """
    probe = FakeDatabaseProbe(reachable=False)
    client = client_with(probe)
    assert client.get("/health").status_code == 503

    probe.reachable = True
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == HEALTHY_BODY


def test_health_requires_no_credentials() -> None:
    """Req: The health endpoint requires no authentication. Scenario: Request without credentials."""
    client = client_with(FakeDatabaseProbe(reachable=True))

    response = client.get("/health", headers={})

    assert response.status_code not in (401, 403)
    assert response.json() == HEALTHY_BODY


@pytest.mark.parametrize(("reachable", "expected_status"), [(True, 200), (False, 503)])
def test_head_answers_the_same_status_as_get_with_no_body(reachable: bool, expected_status: int) -> None:
    """Req: The health endpoint accepts only read requests. Scenario: HEAD request to the health endpoint."""
    client = client_with(FakeDatabaseProbe(reachable=reachable))

    head = client.head("/health")
    get = client.get("/health")

    assert head.status_code == get.status_code == expected_status
    assert head.content == b""


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_write_methods_answer_405(method: str) -> None:
    """Req: The health endpoint accepts only read requests. Scenario: POST to the health endpoint."""
    client = client_with(FakeDatabaseProbe(reachable=True))

    response = client.request(method, "/health")

    assert response.status_code == 405
