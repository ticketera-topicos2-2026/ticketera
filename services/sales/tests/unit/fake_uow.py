"""Pure in-memory test double of UnitOfWork for unit tests."""

from typing import Any

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
        self._inventory_snapshot: dict[Any, Any] | None = None
        self._orders_snapshot: dict[Any, Any] | None = None
        self._idempotency_snapshot: dict[Any, Any] | None = None

    def __enter__(self) -> "InMemoryUnitOfWork":
        inv: Any = self.inventory_repo
        ord_: Any = self.order_repo
        idem: Any = self.idempotency_store
        if hasattr(inv, "seats"):
            self._inventory_snapshot = dict(inv.seats)
        if hasattr(ord_, "orders"):
            self._orders_snapshot = dict(ord_.orders)
        if hasattr(idem, "records"):
            self._idempotency_snapshot = dict(idem.records)
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        if exc_type is not None:
            self.rollback()

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True
        inv: Any = self.inventory_repo
        ord_: Any = self.order_repo
        idem: Any = self.idempotency_store
        if self._inventory_snapshot is not None:
            inv.seats = dict(self._inventory_snapshot)
        if self._orders_snapshot is not None:
            ord_.orders = dict(self._orders_snapshot)
        if self._idempotency_snapshot is not None:
            idem.records = dict(self._idempotency_snapshot)
