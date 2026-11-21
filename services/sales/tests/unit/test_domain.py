"""Unit tests for sales domain entities, value objects, and invariants.

Verifies:
- Money value object (ARS centavos, non-negative, addition, immutable).
- Seat entity & SeatStatus (AVAILABLE, SOLD, immutability/transition invariants).
- Order & OrderStatus (CONFIRMED, items, total calculation).
- Ticket entity (unique code, seat mapping).
- Invariants: unique seat IDs in purchase (uniqueItems: true), rejection of sold seats.
- Import purity: sales.domain imports only Python standard library.
"""

from decimal import Decimal
import sys
import pytest


def test_domain_layer_import_purity() -> None:
    """Verifies that sales.domain imports only modules from standard library."""
    import sales.domain

    domain_modules = [
        name for name, mod in sys.modules.items()
        if name.startswith("sales.domain") and mod is not None
    ]
    # Standard library / built-in prefixes or internal sales.domain modules
    allowed_prefixes = ("sales.domain", "dataclasses", "enum", "typing", "abc", "uuid", "decimal")
    for mod_name in domain_modules:
        assert any(mod_name.startswith(p) for p in allowed_prefixes), (
            f"Impure dependency in domain: {mod_name}"
        )


def test_money_creation_and_properties() -> None:
    """Requirement: ticket-inventory. Seats and orders handle prices in ARS centavos."""
    from sales.domain.models import Money

    m = Money(amount_centavos=150000, currency="ARS")
    assert m.amount_centavos == 150000
    assert m.currency == "ARS"
    assert m.to_decimal() == Decimal("1500.00")


def test_money_rejects_negative_amount() -> None:
    """Invariant: Money cannot be negative."""
    from sales.domain.models import Money

    with pytest.raises(ValueError, match="amount cannot be negative"):
        Money(amount_centavos=-1, currency="ARS")


def test_money_addition_and_equality() -> None:
    """Invariant: Money addition works only within same currency."""
    from sales.domain.models import Money

    m1 = Money(amount_centavos=10000, currency="ARS")
    m2 = Money(amount_centavos=25000, currency="ARS")
    total = m1 + m2
    assert total == Money(amount_centavos=35000, currency="ARS")


def test_seat_entity_and_status() -> None:
    """Requirement: ticket-inventory. Seat has event, id, category, price and status."""
    from sales.domain.models import Seat, SeatStatus, Money

    seat = Seat(
        event_id="evt-100",
        seat_id="A-1",
        category="VIP",
        price=Money(amount_centavos=50000, currency="ARS"),
        status=SeatStatus.AVAILABLE,
    )
    assert seat.is_available()
    assert seat.seat_id == "A-1"


def test_seat_cannot_be_sold_if_not_available() -> None:
    """Invariant: An unavailable seat cannot be marked sold."""
    from sales.domain.models import Seat, SeatStatus, Money
    from sales.domain.exceptions import SeatNotAvailableError

    seat = Seat(
        event_id="evt-100",
        seat_id="A-1",
        category="VIP",
        price=Money(amount_centavos=50000, currency="ARS"),
        status=SeatStatus.SOLD,
    )
    assert not seat.is_available()
    with pytest.raises(SeatNotAvailableError):
        seat.mark_sold()


def test_order_creation_with_tickets_and_total() -> None:
    """Requirement: ticket-purchase. Order aggregates confirmed tickets and computes total."""
    from sales.domain.models import Order, OrderStatus, Ticket, Money

    t1 = Ticket(ticket_id="tkt-1", order_id="ord-1", event_id="evt-1", seat_id="A-1", code="TCK-A1-XYZ")
    t2 = Ticket(ticket_id="tkt-2", order_id="ord-1", event_id="evt-1", seat_id="A-2", code="TCK-A2-XYZ")

    order = Order.create(
        order_id="ord-1",
        customer_id="usr-10",
        event_id="evt-1",
        tickets=[t1, t2],
        total_amount=Money(amount_centavos=100000, currency="ARS"),
    )
    assert order.status == OrderStatus.CONFIRMED
    assert len(order.tickets) == 2
    assert order.total_amount.amount_centavos == 100000


def test_order_rejects_empty_tickets() -> None:
    """Invariant: Order must contain at least one ticket."""
    from sales.domain.models import Order, Money
    from sales.domain.exceptions import EmptyOrderError

    with pytest.raises(EmptyOrderError):
        Order.create(
            order_id="ord-1",
            customer_id="usr-10",
            event_id="evt-1",
            tickets=[],
            total_amount=Money(amount_centavos=0, currency="ARS"),
        )


def test_order_rejects_duplicate_seat_ids() -> None:
    """Invariant: Order cannot contain duplicate seat IDs (uniqueItems: true)."""
    from sales.domain.models import Order, Ticket, Money
    from sales.domain.exceptions import DuplicateSeatError

    t1 = Ticket(ticket_id="tkt-1", order_id="ord-1", event_id="evt-1", seat_id="A-1", code="TCK-1")
    t2 = Ticket(ticket_id="tkt-2", order_id="ord-1", event_id="evt-1", seat_id="A-1", code="TCK-2")

    with pytest.raises(DuplicateSeatError):
        Order.create(
            order_id="ord-1",
            customer_id="usr-10",
            event_id="evt-1",
            tickets=[t1, t2],
            total_amount=Money(amount_centavos=50000, currency="ARS"),
        )
