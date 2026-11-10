"""Tests of the SQLAlchemy database probe adapter (spec platform/service-health, DS-11)."""

import os
import time

import pytest

from catalog.infrastructure.database_probe import SqlAlchemyDatabaseProbe

# A non-routable address: the connection attempt hangs until the connect timeout expires.
BLACKHOLE_URL = "postgresql+psycopg://catalog:catalog@10.255.255.1:5432/catalog"
UNKNOWN_HOST_URL = "postgresql+psycopg://catalog:catalog@no-such-database-host:5432/catalog"


def test_probe_reports_an_unreachable_database_within_three_seconds() -> None:
    """Req: The health endpoint reports an unreachable database. Scenario: Database stopped
    (the connect timeout keeps the answer under 3 seconds).
    """
    probe = SqlAlchemyDatabaseProbe(BLACKHOLE_URL)

    started = time.monotonic()
    reachable = probe.is_reachable()
    elapsed = time.monotonic() - started

    assert reachable is False
    assert elapsed < 3


def test_probe_reports_an_unknown_host_as_unreachable_without_raising() -> None:
    """Req: The health endpoint reports an unreachable database. Scenario: Database stopped
    (a stopped container's host name no longer resolves).
    """
    probe = SqlAlchemyDatabaseProbe(UNKNOWN_HOST_URL)

    assert probe.is_reachable() is False


@pytest.mark.skipif(
    "CATALOG_TEST_DATABASE_URL" not in os.environ,
    reason="needs a running PostgreSQL; set CATALOG_TEST_DATABASE_URL",
)
def test_probe_reports_a_running_database_as_reachable_within_one_second() -> None:
    """Req: The health endpoint reports a healthy service. Scenario: Healthy catalog service
    (the SELECT 1 probe against a real PostgreSQL answers within 1 second).
    """
    probe = SqlAlchemyDatabaseProbe(os.environ["CATALOG_TEST_DATABASE_URL"])

    started = time.monotonic()
    reachable = probe.is_reachable()
    elapsed = time.monotonic() - started

    assert reachable is True
    assert elapsed < 1
