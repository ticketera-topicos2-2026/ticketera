"""Unit of Work port protocol for transactional application use cases."""

from typing import Protocol

from sales.application.ports import (
    IdempotencyStore,
    InventoryRepository,
    OrderRepository,
)


class UnitOfWork(Protocol):
    """Port managing transactional boundaries and repository access."""

    inventory_repo: InventoryRepository
    order_repo: OrderRepository
    idempotency_store: IdempotencyStore

    def __enter__(self) -> "UnitOfWork": ...

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...
