"""Pure domain entities and value objects for ticket sales (hexagonal core)."""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Self

from sales.domain.exceptions import (
    DuplicateSeatError,
    EmptyOrderError,
    IncompatibleCurrencyError,
    SeatNotAvailableError,
)


@dataclass(frozen=True)
class Money:
    """Monetary value object handling currency and non-negative amounts in centavos."""

    amount_centavos: int
    currency: str = "ARS"

    def __post_init__(self) -> None:
        if self.amount_centavos < 0:
            raise ValueError("amount cannot be negative")

    def to_decimal(self) -> Decimal:
        """Returns the monetary value as standard decimal units (e.g. 1500.00)."""
        return (Decimal(self.amount_centavos) / Decimal(100)).quantize(Decimal("0.01"))

    def __add__(self, other: Self) -> "Money":
        if not isinstance(other, Money) or self.currency != other.currency:
            raise IncompatibleCurrencyError("Cannot add money of different currencies")
        return Money(amount_centavos=self.amount_centavos + other.amount_centavos, currency=self.currency)


class SeatStatus(StrEnum):
    """Lifecycle status of a seat inventory item."""

    AVAILABLE = "AVAILABLE"
    SOLD = "SOLD"


@dataclass
class Seat:
    """Individual seat entity associated with an event."""

    event_id: str
    seat_id: str
    category: str
    price: Money
    status: SeatStatus = SeatStatus.AVAILABLE

    def is_available(self) -> bool:
        """Checks if the seat is available for purchase."""
        return self.status == SeatStatus.AVAILABLE

    def mark_sold(self) -> None:
        """Transitions seat to SOLD or raises if unavailable."""
        if not self.is_available():
            raise SeatNotAvailableError(f"Seat {self.seat_id} is not available (status: {self.status})")
        self.status = SeatStatus.SOLD


class OrderStatus(StrEnum):
    """Status of a customer ticket purchase order."""

    CONFIRMED = "CONFIRMED"


@dataclass(frozen=True)
class Ticket:
    """Issued ticket entity mapping a customer's order to a confirmed seat."""

    ticket_id: str
    order_id: str
    event_id: str
    seat_id: str
    code: str


@dataclass
class Order:
    """Customer purchase order aggregate holding confirmed tickets."""

    order_id: str
    customer_id: str
    event_id: str
    tickets: list[Ticket]
    total_amount: Money
    status: OrderStatus = OrderStatus.CONFIRMED

    @classmethod
    def create(
        cls,
        order_id: str,
        customer_id: str,
        event_id: str,
        tickets: list[Ticket],
        total_amount: Money,
    ) -> "Order":
        """Factory enforcing domain invariants on purchase creation."""
        if not tickets:
            raise EmptyOrderError("Order must contain at least one ticket")

        seat_ids = [t.seat_id for t in tickets]
        if len(seat_ids) != len(set(seat_ids)):
            raise DuplicateSeatError("Order cannot contain duplicate seat IDs")

        return cls(
            order_id=order_id,
            customer_id=customer_id,
            event_id=event_id,
            tickets=tickets,
            total_amount=total_amount,
            status=OrderStatus.CONFIRMED,
        )
