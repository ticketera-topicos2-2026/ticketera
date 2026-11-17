"""Router of the health endpoint (spec platform/service-health)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from catalog.application.health import DatabaseProbe, check_health

SERVICE_NAME = "catalog"

router = APIRouter()


def get_database_probe(request: Request) -> DatabaseProbe:
    probe: DatabaseProbe = request.app.state.database_probe
    return probe


# A plain `def` runs in the thread pool, so the blocking probe never stalls the event loop.
@router.api_route("/health", methods=["GET", "HEAD"])
def health(probe: Annotated[DatabaseProbe, Depends(get_database_probe)]) -> JSONResponse:
    """Reports the service status and its database connectivity; needs no credentials."""
    report = check_health(SERVICE_NAME, probe)
    return JSONResponse(
        status_code=200 if report.is_healthy else 503,
        content={"status": report.status, "service": report.service, "database": report.database},
    )
