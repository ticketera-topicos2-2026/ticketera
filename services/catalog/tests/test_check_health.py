"""Unit tests of the check-health use case, with no FastAPI and no database (spec platform/service-health)."""

from catalog.application.health import HealthReport, check_health


class StubProbe:
    def __init__(self, reachable: bool) -> None:
        self.reachable = reachable

    def is_reachable(self) -> bool:
        return self.reachable


class RaisingProbe:
    def is_reachable(self) -> bool:
        raise OSError("network down")


def test_reachable_database_gives_a_healthy_report() -> None:
    """Req: The health endpoint reports a healthy service. Scenario: Healthy catalog service."""
    report = check_health("catalog", StubProbe(reachable=True))

    assert report == HealthReport(status="ok", service="catalog", database="ok")
    assert report.is_healthy


def test_unreachable_database_gives_an_unavailable_report() -> None:
    """Req: The health endpoint reports an unreachable database. Scenario: Database stopped."""
    report = check_health("catalog", StubProbe(reachable=False))

    assert report == HealthReport(status="unavailable", service="catalog", database="unavailable")
    assert not report.is_healthy


def test_a_probe_error_counts_as_an_unreachable_database() -> None:
    """Req: The health response reveals no internal details. Scenario: Response while the database is
    unavailable (an adapter error becomes an unavailable report, never an error message).
    """
    report = check_health("catalog", RaisingProbe())

    assert report == HealthReport(status="unavailable", service="catalog", database="unavailable")
