"""Unit tests for sales application use cases, ports, and fake adapters (TDD).

Verifies:
- Ports: InventoryRepository, OrderRepository, IdempotencyStore.
- Use cases:
  - InitializeInventory (admin creates seats with price in ARS).
  - GetAvailableSeats (queries seats by status).
  - PurchaseTickets (reserves idempotency key, locks seats, creates order + tickets, replay on key match).
  - GetOrder (retrieves order with customer ownership check / BOLA).
- Business error handling & isolation using in-memory fake repositories.
"""

from dataclasses import dataclass
from typing import Any

import pytest

from sales.domain.exceptions import SeatNotAvailableError
from sales.domain.models import Money, Order, Seat, SeatStatus, Ticket


class FakeInventoryRepository:
    """In-memory fake repository for seat inventory."""

    def __init__(self) -> None:
        self.seats: dict[tuple[str, str], Seat] = {}

    def save_all(self, seats: list[Seat]) -> None:
        for s in seats:
            self.seats[(s.event_id, s.seat_id)] = s

    def find_by_event(self, event_id: str, status: SeatStatus | None = None) -> list[Seat]:
        return [
            s
            for s in self.seats.values()
            if s.event_id == event_id and (status is None or s.status == status)
        ]

    def find_by_seats_for_update(self, event_id: str, seat_ids: list[str]) -> list[Seat]:
        # Emulates SELECT ... ORDER BY seat_id FOR UPDATE
        sorted_ids = sorted(seat_ids)
        result = []
        for sid in sorted_ids:
            key = (event_id, sid)
            if key in self.seats:
                result.append(self.seats[key])
        return result

    def exists_any(self, event_id: str) -> bool:
        return any(s.event_id == event_id for s in self.seats.values())


class FakeOrderRepository:
    """In-memory fake repository for orders and tickets."""

    def __init__(self) -> None:
        self.orders: dict[str, Order] = {}

    def save(self, order: Order) -> None:
        self.orders[order.order_id] = order

    def find_by_id(self, order_id: str) -> Order | None:
        return self.orders.get(order_id)


@dataclass
class IdempotencyRecord:
    customer_id: str
    key: str
    request_hash: str
    response_status: int | None = None
    response_body: dict[str, object] | None = None


class FakeIdempotencyStore:
    """In-memory fake store for idempotency keys."""

    def __init__(self) -> None:
        self.records: dict[tuple[str, str], IdempotencyRecord] = {}

    def reserve(self, customer_id: str, key: str, request_hash: str) -> bool:
        """Returns True if reserved (1 row inserted), False if already exists (0 rows)."""
        composite_key = (customer_id, key)
        if composite_key in self.records:
            return False
        self.records[composite_key] = IdempotencyRecord(
            customer_id=customer_id, key=key, request_hash=request_hash
        )
        return True

    def get(self, customer_id: str, key: str) -> Any:
        return self.records.get((customer_id, key))

    def update_response(self, customer_id: str, key: str, status: int, body: dict[str, Any]) -> None:
        rec = self.records.get((customer_id, key))
        if rec:
            rec.response_status = status
            rec.response_body = body

    def remove(self, customer_id: str, key: str) -> None:
        self.records.pop((customer_id, key), None)


def test_initialize_inventory_use_case() -> None:
    """Requirement: ticket-inventory. Admin initializes seats with ARS prices."""
    from sales.application.dtos import SeatInitDTO
    from sales.application.inventory import InitializeInventoryCommand, InitializeInventoryUseCase

    repo = FakeInventoryRepository()
    use_case = InitializeInventoryUseCase(repo)

    seats_to_init = [
        SeatInitDTO(seat_id="A-1", category="VIP", price_centavos=100000),
        SeatInitDTO(seat_id="A-2", category="VIP", price_centavos=100000),
    ]

    use_case.execute(InitializeInventoryCommand(event_id="evt-1", seats=seats_to_init))

    saved_seats = repo.find_by_event("evt-1")
    assert len(saved_seats) == 2
    assert all(s.status == SeatStatus.AVAILABLE for s in saved_seats)


def test_initialize_inventory_rejects_reinitialization() -> None:
    """Requirement: ticket-inventory. Conflict if event inventory already initialized."""
    from sales.application.dtos import SeatInitDTO
    from sales.application.exceptions import InventoryAlreadyInitializedError
    from sales.application.inventory import InitializeInventoryCommand, InitializeInventoryUseCase

    repo = FakeInventoryRepository()
    use_case = InitializeInventoryUseCase(repo)

    seats_to_init = [SeatInitDTO(seat_id="A-1", category="VIP", price_centavos=50000)]
    use_case.execute(InitializeInventoryCommand(event_id="evt-1", seats=seats_to_init))

    with pytest.raises(InventoryAlreadyInitializedError):
        use_case.execute(InitializeInventoryCommand(event_id="evt-1", seats=seats_to_init))


def test_get_available_seats_use_case() -> None:
    """Requirement: ticket-inventory. Query available seats for an event."""
    from sales.application.inventory import GetAvailableSeatsUseCase

    repo = FakeInventoryRepository()
    repo.save_all(
        [
            Seat("evt-1", "A-1", "VIP", Money(50000), SeatStatus.AVAILABLE),
            Seat("evt-1", "A-2", "VIP", Money(50000), SeatStatus.SOLD),
            Seat("evt-2", "B-1", "General", Money(20000), SeatStatus.AVAILABLE),
        ]
    )

    use_case = GetAvailableSeatsUseCase(repo)
    available_evt1 = use_case.execute(event_id="evt-1", status=SeatStatus.AVAILABLE)

    assert len(available_evt1) == 1
    assert available_evt1[0].seat_id == "A-1"


def test_purchase_tickets_successful_execution() -> None:
    """Requirement: ticket-purchase & idempotency. Direct atomic purchase."""
    from sales.application.orders import PurchaseTicketsCommand, PurchaseTicketsUseCase

    inventory_repo = FakeInventoryRepository()
    inventory_repo.save_all(
        [
            Seat("evt-1", "A-1", "VIP", Money(50000), SeatStatus.AVAILABLE),
            Seat("evt-1", "A-2", "VIP", Money(50000), SeatStatus.AVAILABLE),
        ]
    )
    order_repo = FakeOrderRepository()
    idempotency_store = FakeIdempotencyStore()

    use_case = PurchaseTicketsUseCase(inventory_repo, order_repo, idempotency_store)

    cmd = PurchaseTicketsCommand(
        customer_id="usr-10",
        event_id="evt-1",
        seat_ids=["A-1", "A-2"],
        idempotency_key="key-uuid-1",
    )

    result = use_case.execute(cmd)
    assert result.status == 201
    assert result.is_replay is False
    assert result.order.customer_id == "usr-10"
    assert len(result.order.tickets) == 2

    # Verify seats are now SOLD
    seats = inventory_repo.find_by_seats_for_update("evt-1", ["A-1", "A-2"])
    assert all(s.status == SeatStatus.SOLD for s in seats)


def test_purchase_tickets_replay_on_identical_key() -> None:
    """Requirement: idempotency. Replaying with identical key returns cached 201."""
    from sales.application.orders import PurchaseTicketsCommand, PurchaseTicketsUseCase

    inventory_repo = FakeInventoryRepository()
    inventory_repo.save_all(
        [
            Seat("evt-1", "A-1", "VIP", Money(50000), SeatStatus.AVAILABLE),
        ]
    )
    order_repo = FakeOrderRepository()
    idempotency_store = FakeIdempotencyStore()

    use_case = PurchaseTicketsUseCase(inventory_repo, order_repo, idempotency_store)

    cmd = PurchaseTicketsCommand(
        customer_id="usr-10",
        event_id="evt-1",
        seat_ids=["A-1"],
        idempotency_key="key-uuid-1",
    )

    first_res = use_case.execute(cmd)
    assert first_res.status == 201
    assert first_res.is_replay is False

    # Second execution with exact same key and payload
    second_res = use_case.execute(cmd)
    assert second_res.status == 201
    assert second_res.is_replay is True
    assert second_res.order.order_id == first_res.order.order_id


def test_purchase_tickets_rejects_payload_mismatch_with_same_key() -> None:
    """Requirement: idempotency. Key reuse with different seats raises 422 mismatch."""
    from sales.application.exceptions import IdempotencyKeyMismatchError
    from sales.application.orders import PurchaseTicketsCommand, PurchaseTicketsUseCase

    inventory_repo = FakeInventoryRepository()
    inventory_repo.save_all(
        [
            Seat("evt-1", "A-1", "VIP", Money(50000), SeatStatus.AVAILABLE),
            Seat("evt-1", "A-2", "VIP", Money(50000), SeatStatus.AVAILABLE),
        ]
    )
    order_repo = FakeOrderRepository()
    idempotency_store = FakeIdempotencyStore()

    use_case = PurchaseTicketsUseCase(inventory_repo, order_repo, idempotency_store)

    cmd1 = PurchaseTicketsCommand(
        customer_id="usr-10",
        event_id="evt-1",
        seat_ids=["A-1"],
        idempotency_key="key-uuid-1",
    )
    use_case.execute(cmd1)

    cmd2 = PurchaseTicketsCommand(
        customer_id="usr-10",
        event_id="evt-1",
        seat_ids=["A-2"],  # Different seat with same key!
        idempotency_key="key-uuid-1",
    )
    with pytest.raises(IdempotencyKeyMismatchError):
        use_case.execute(cmd2)


def test_purchase_tickets_rejects_unavailable_seat() -> None:
    """Requirement: ticket-purchase. Returns conflict when seat is already SOLD."""
    from sales.application.orders import PurchaseTicketsCommand, PurchaseTicketsUseCase

    inventory_repo = FakeInventoryRepository()
    inventory_repo.save_all(
        [
            Seat("evt-1", "A-1", "VIP", Money(50000), SeatStatus.SOLD),
        ]
    )
    order_repo = FakeOrderRepository()
    idempotency_store = FakeIdempotencyStore()

    use_case = PurchaseTicketsUseCase(inventory_repo, order_repo, idempotency_store)

    cmd = PurchaseTicketsCommand(
        customer_id="usr-10",
        event_id="evt-1",
        seat_ids=["A-1"],
        idempotency_key="key-uuid-1",
    )
    with pytest.raises(SeatNotAvailableError):
        use_case.execute(cmd)

    # Verify idempotency key was rolled back / removed
    assert idempotency_store.get("usr-10", "key-uuid-1") is None


def test_get_order_with_bola_authorization() -> None:
    """Requirement: ticket-purchase & BOLA. Customer can only access own order unless ADMIN."""
    from sales.application.exceptions import OrderNotFoundError
    from sales.application.orders import GetOrderUseCase

    order_repo = FakeOrderRepository()
    t1 = Ticket(ticket_id="t1", order_id="ord-1", event_id="evt-1", seat_id="A-1", code="C-1")
    order = Order.create("ord-1", "usr-10", "evt-1", [t1], Money(50000))
    order_repo.save(order)

    use_case = GetOrderUseCase(order_repo)

    # Owner customer: success
    res = use_case.execute(order_id="ord-1", requesting_user_id="usr-10", is_admin=False)
    assert res.order_id == "ord-1"

    # Admin: success
    res_admin = use_case.execute(order_id="ord-1", requesting_user_id="admin-99", is_admin=True)
    assert res_admin.order_id == "ord-1"

    # Other customer: raises OrderNotFoundError (404, not 403, preventing BOLA probing)
    with pytest.raises(OrderNotFoundError):
        use_case.execute(order_id="ord-1", requesting_user_id="usr-20", is_admin=False)
