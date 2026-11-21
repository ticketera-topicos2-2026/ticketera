"""Pure in-memory test double of UnitOfWork for unit tests."""

from sales.application.ports import (
    IdempotencyStore,
    InventoryRepository,
    OrderRepository,
)
from sales.application.uow import UnitOfWork


class InMemoryUnitOfWork(UnitOfWork):
    """Fake Unit of Work storing state in memory without database dependencies."""

    def __init__(
        self,
        inventory_repo: InventoryRepository,
        order_repo: OrderRepository,
        idempotency_store: IdempotencyStore,
    ) -> None:
        self.inventory_repo = inventory_repo
        self.order_repo = order_repo
        self.idempotency_store = idempotency_store
        self.committed = False
        self.rolled_back = False

    def __enter__(self) -> "InMemoryUnitOfWork":
        if hasattr(self.inventory_repo, "seats"):
            self._inventory_snapshot = dict(self.inventory_repo.seats)
        if hasattr(self.order_repo, "orders"):
            self._orders_snapshot = dict(self.order_repo.orders)
        if hasattr(self.idempotency_store, "records"):
            self._idempotency_snapshot = dict(self.idempotency_store.records)
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        if exc_type is not None:
            self.rollback()

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True
        if hasattr(self, "_inventory_snapshot"):
            self.inventory_repo.seats = dict(self._inventory_snapshot)
        if hasattr(self, "_orders_snapshot"):
            self.order_repo.orders = dict(self._orders_snapshot)
        if hasattr(self, "_idempotency_snapshot"):
            self.idempotency_store.records = dict(self._idempotency_snapshot)
