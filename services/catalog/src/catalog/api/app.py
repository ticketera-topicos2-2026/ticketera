"""Application factory of the catalog service."""

from fastapi import FastAPI

from catalog.api.health import SERVICE_NAME
from catalog.api.health import router as health_router
from catalog.api.request_log import RequestLogMiddleware
from catalog.application.health import DatabaseProbe


def create_app(database_probe: DatabaseProbe) -> FastAPI:
    # The gateway publishes this service under /api/catalog (D-29, DS-11).
    app = FastAPI(title="catalog", root_path="/api/catalog")
    app.state.database_probe = database_probe
    app.include_router(health_router)
    # Added last, so it wraps routing, dependencies and exception handlers: it times the whole request
    # and sees every status (e1-request-log, RL-05).
    app.add_middleware(RequestLogMiddleware, service_name=SERVICE_NAME)
    return app
