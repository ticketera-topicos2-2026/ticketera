"""Application factory of the sales service."""

from fastapi import FastAPI

from sales.api.health import router as health_router
from sales.api.routes import router as sales_router
from sales.application.health import DatabaseProbe
from sales.application.inventory import GetAvailableSeatsUseCase, InitializeInventoryUseCase
from sales.application.orders import GetOrderUseCase, PurchaseTicketsUseCase
from sales.application.ports import IdempotencyStore, InventoryRepository, OrderRepository


def create_app(
    database_probe: DatabaseProbe,
    inventory_repo: InventoryRepository | None = None,
    order_repo: OrderRepository | None = None,
    idempotency_store: IdempotencyStore | None = None,
) -> FastAPI:
    # The gateway publishes this service under /api/sales (D-29, DS-11).
    app = FastAPI(title="sales", root_path="/api/sales")
    app.state.database_probe = database_probe

    if inventory_repo is not None:
        app.state.inventory_repo = inventory_repo
        app.state.init_inventory_use_case = InitializeInventoryUseCase(inventory_repo)
        app.state.get_seats_use_case = GetAvailableSeatsUseCase(inventory_repo)

    if order_repo is not None:
        app.state.order_repo = order_repo
        app.state.get_order_use_case = GetOrderUseCase(order_repo)

    if idempotency_store is not None:
        app.state.idempotency_store = idempotency_store

    if inventory_repo is not None and order_repo is not None and idempotency_store is not None:
        app.state.purchase_tickets_use_case = PurchaseTicketsUseCase(
            inventory_repo=inventory_repo,
            order_repo=order_repo,
            idempotency_store=idempotency_store,
        )

    app.include_router(health_router)
    app.include_router(sales_router)
    return app
