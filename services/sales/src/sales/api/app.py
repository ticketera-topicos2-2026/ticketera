"""Application factory of the sales service."""

from collections.abc import Callable

from fastapi import FastAPI
from sqlalchemy.orm import Session, sessionmaker

from sales.api.health import router as health_router
from sales.api.routes import router as sales_router
from sales.application.health import DatabaseProbe
from sales.application.ports import InventoryRepository, OrderRepository
from sales.application.uow import UnitOfWork
from sales.infrastructure.repositories import PostgresInventoryRepository, PostgresOrderRepository
from sales.infrastructure.uow import SqlAlchemyUnitOfWork


def create_app(
    database_probe: DatabaseProbe,
    session_factory: sessionmaker[Session] | None = None,
    uow_factory: Callable[[], UnitOfWork] | None = None,
    inventory_repo_factory: Callable[[], InventoryRepository] | None = None,
    order_repo_factory: Callable[[], OrderRepository] | None = None,
) -> FastAPI:
    # The gateway publishes this service under /api/sales (D-29, DS-11).
    app = FastAPI(title="sales", root_path="/api/sales")
    app.state.database_probe = database_probe

    if session_factory is not None and uow_factory is None:
        app.state.uow_factory = lambda: SqlAlchemyUnitOfWork(session_factory)
        app.state.inventory_repo_factory = lambda: PostgresInventoryRepository(session_factory())
        app.state.order_repo_factory = lambda: PostgresOrderRepository(session_factory())
    else:
        app.state.uow_factory = uow_factory
        app.state.inventory_repo_factory = inventory_repo_factory
        app.state.order_repo_factory = order_repo_factory

    app.include_router(health_router)
    app.include_router(sales_router)
    return app
