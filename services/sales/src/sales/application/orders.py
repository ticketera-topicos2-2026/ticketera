"""Order and ticket purchase use cases."""

import hashlib
import uuid
from dataclasses import dataclass

from sales.application.exceptions import IdempotencyKeyMismatchError, OrderNotFoundError
from sales.application.ports import OrderRepository
from sales.application.uow import UnitOfWork
from sales.domain.exceptions import SeatNotAvailableError
from sales.domain.models import Money, Order, Ticket


@dataclass(frozen=True)
class PurchaseTicketsCommand:
    customer_id: str
    event_id: str
    seat_ids: list[str]
    idempotency_key: str


@dataclass(frozen=True)
class PurchaseResult:
    status: int
    order: Order
    is_replay: bool


def compute_request_hash(event_id: str, seat_ids: list[str]) -> str:
    """Calculates deterministic hash over event_id and sorted seat_ids."""
    normalized = f"{event_id}:{','.join(sorted(seat_ids))}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class PurchaseTicketsUseCase:
    """Executes atomic, customer-scoped ticket purchase with idempotency."""

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self, cmd: PurchaseTicketsCommand) -> PurchaseResult:
        request_hash = compute_request_hash(cmd.event_id, cmd.seat_ids)

        with self.uow:
            # 1. Step 1: Reserve idempotency key FIRST before touching seats
            reserved = self.uow.idempotency_store.reserve(
                customer_id=cmd.customer_id,
                key=cmd.idempotency_key,
                request_hash=request_hash,
            )

            if not reserved:
                # Key already exists: check hash and retrieve confirmed state
                record = self.uow.idempotency_store.get(cmd.customer_id, cmd.idempotency_key)
                if record and record.request_hash != request_hash:
                    self.uow.rollback()
                    raise IdempotencyKeyMismatchError("Idempotency key payload mismatch")

                if record and record.response_body and "order_id" in record.response_body:
                    existing_order = self.uow.order_repo.find_by_id(record.response_body["order_id"])
                    if existing_order:
                        self.uow.rollback()
                        return PurchaseResult(status=201, order=existing_order, is_replay=True)

                # Concurrent in-flight request on same key without response yet
                self.uow.rollback()
                raise SeatNotAvailableError("An identical purchase request is currently in progress")

            # 2. Lock selected seats in strict order
            locked_seats = self.uow.inventory_repo.find_by_seats_for_update(cmd.event_id, cmd.seat_ids)

            # Check that all requested seats exist and are AVAILABLE
            found_ids = {s.seat_id for s in locked_seats}
            missing_or_unavailable = [
                sid
                for sid in cmd.seat_ids
                if sid not in found_ids
                or not any(s.seat_id == sid and s.is_available() for s in locked_seats)
            ]
            if missing_or_unavailable:
                self.uow.rollback()
                raise SeatNotAvailableError(f"Seats not available: {', '.join(missing_or_unavailable)}")

            # 3. Transition seats to SOLD
            total_centavos = sum(s.price.amount_centavos for s in locked_seats)
            for s in locked_seats:
                s.mark_sold()
            self.uow.inventory_repo.save_all(locked_seats)

            # 4. Create Order and Tickets
            order_id = f"ord-{uuid.uuid4().hex[:8]}"
            tickets = [
                Ticket(
                    ticket_id=f"tkt-{uuid.uuid4().hex[:8]}",
                    order_id=order_id,
                    event_id=cmd.event_id,
                    seat_id=s.seat_id,
                    code=f"TCK-{s.seat_id}-{uuid.uuid4().hex[:6].upper()}",
                )
                for s in locked_seats
            ]

            order = Order.create(
                order_id=order_id,
                customer_id=cmd.customer_id,
                event_id=cmd.event_id,
                tickets=tickets,
                total_amount=Money(amount_centavos=total_centavos, currency="ARS"),
            )
            self.uow.order_repo.save(order)

            # 5. Update Idempotency Record with response
            response_payload = {
                "order_id": order.order_id,
                "status": order.status.value,
            }
            self.uow.idempotency_store.update_response(
                customer_id=cmd.customer_id,
                key=cmd.idempotency_key,
                status=201,
                body=response_payload,
            )

            # 6. Commit transaction atomically
            self.uow.commit()

            return PurchaseResult(status=201, order=order, is_replay=False)


class GetOrderUseCase:
    """Retrieves order details enforcing BOLA customer isolation."""

    def __init__(self, order_repo: OrderRepository) -> None:
        self.order_repo = order_repo

    def execute(self, order_id: str, requesting_user_id: str, is_admin: bool) -> Order:
        order = self.order_repo.find_by_id(order_id)
        if not order:
            raise OrderNotFoundError(f"Order {order_id} not found")

        # BOLA protection: user must own the order or be an ADMIN
        if not is_admin and order.customer_id != requesting_user_id:
            raise OrderNotFoundError(f"Order {order_id} not found")

        return order
