"""Application factory of the catalog service."""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import FastAPI

from catalog.api.errors import install_error_handlers
from catalog.api.health import router as health_router
from catalog.api.routes import manage_router, public_router
from catalog.application.events import CatalogService
from catalog.application.health import DatabaseProbe
from catalog.application.ports import UnitOfWork


def _no_database() -> UnitOfWork:
    raise RuntimeError("The catalog app was created without a unit of work factory")


def _utc_now() -> datetime:
    return datetime.now(UTC)


def create_app(
    database_probe: DatabaseProbe,
    uow_factory: Callable[[], UnitOfWork] = _no_database,
    clock: Callable[[], datetime] = _utc_now,
) -> FastAPI:
    # The gateway publishes this service under /api/catalog (D-29, DS-11).
    app = FastAPI(title="catalog", root_path="/api/catalog")
    app.state.database_probe = database_probe
    app.state.catalog_service = CatalogService(uow_factory=uow_factory, clock=clock, new_id=uuid4)
    install_error_handlers(app)
    app.include_router(health_router)
    app.include_router(public_router)
    app.include_router(manage_router)
    return app
