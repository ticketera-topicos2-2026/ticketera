"""Repository and storage port protocols for sales application layer."""

from dataclasses import dataclass
from typing import Any, Protocol

from sales.domain.models import Order, Seat, SeatStatus


@dataclass(frozen=True)
class StoredIdempotencyRecord:
    customer_id: str
    key: str
    request_hash: str
    response_status: int | None = None
    response_body: dict[str, Any] | None = None


class InventoryRepository(Protocol):
    """Port for seat inventory persistence."""

    def save_all(self, seats: list[Seat]) -> None:
        """Persists a collection of seat entities."""
        ...

    def find_by_event(self, event_id: str, status: SeatStatus | None = None) -> list[Seat]:
        """Queries seats for an event, optionally filtered by status."""
        ...

    def find_by_seats_for_update(self, event_id: str, seat_ids: list[str]) -> list[Seat]:
        """Locks and returns selected seats in strict seat_id order."""
        ...

    def exists_any(self, event_id: str) -> bool:
        """Returns True if any seats are already initialized for the event."""
        ...


class OrderRepository(Protocol):
    """Port for order and ticket persistence."""

    def save(self, order: Order) -> None:
        """Persists an order and its associated tickets atomically."""
        ...

    def find_by_id(self, order_id: str) -> Order | None:
        """Finds an order by its unique ID."""
        ...


class IdempotencyStore(Protocol):
    """Port for transactional customer-scoped idempotency keys."""

    def reserve(self, customer_id: str, key: str, request_hash: str) -> bool:
        """Attempts to reserve a key. Returns True if inserted, False if conflict."""
        ...

    def get(self, customer_id: str, key: str) -> StoredIdempotencyRecord | None:
        """Fetches the idempotency record for customer and key."""
        ...

    def update_response(self, customer_id: str, key: str, status: int, body: dict[str, Any]) -> None:
        """Updates the reserved key with the finalized HTTP response status and body."""
        ...

    def remove(self, customer_id: str, key: str) -> None:
        """Removes an uncommitted or failed reservation upon transaction rollback."""
        ...
