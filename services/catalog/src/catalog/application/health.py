"""Check-health use case and its database probe port (spec platform/service-health)."""

import logging
from dataclasses import dataclass
from typing import Literal, Protocol

logger = logging.getLogger(__name__)

ComponentStatus = Literal["ok", "unavailable"]


class DatabaseProbe(Protocol):
    """Port: tells whether the service's database answers right now."""

    def is_reachable(self) -> bool: ...


@dataclass(frozen=True)
class HealthReport:
    """Health of the service; only these three fields ever leave the service (DS-11)."""

    status: ComponentStatus
    service: str
    database: ComponentStatus

    @property
    def is_healthy(self) -> bool:
        return self.status == "ok"


def check_health(service: str, probe: DatabaseProbe) -> HealthReport:
    """Reports the service as healthy only when its database is reachable."""
    try:
        reachable = probe.is_reachable()
    except Exception:
        # The details stay in the service log; the report never carries them.
        logger.exception("Database probe failed")
        reachable = False

    status: ComponentStatus = "ok" if reachable else "unavailable"
    return HealthReport(status=status, service=service, database=status)
