"""PostgreSQL SQLAlchemy repository and store implementations for sales."""

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from sales.application.ports import (
    StoredIdempotencyRecord,
)
from sales.domain.models import Money, Order, OrderStatus, Seat, SeatStatus, Ticket


class PostgresInventoryRepository:
    """SQLAlchemy PostgreSQL implementation of InventoryRepository."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def save_all(self, seats: list[Seat]) -> None:
        for s in seats:
            self.session.execute(
                text(
                    """
                    INSERT INTO seats (event_id, seat_id, category, price_centavos, currency, status)
                    VALUES (:event_id, :seat_id, :category, :price_centavos, :currency, :status)
                    ON CONFLICT (event_id, seat_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        price_centavos = EXCLUDED.price_centavos
                    """
                ),
                {
                    "event_id": s.event_id,
                    "seat_id": s.seat_id,
                    "category": s.category,
                    "price_centavos": s.price.amount_centavos,
                    "currency": s.price.currency,
                    "status": s.status.value,
                },
            )

    def find_by_event(self, event_id: str, status: SeatStatus | None = None) -> list[Seat]:
        query = (
            "SELECT event_id, seat_id, category, price_centavos, currency, status "
            "FROM seats WHERE event_id = :event_id"
        )
        params: dict[str, Any] = {"event_id": event_id}
        if status:
            query += " AND status = :status"
            params["status"] = status.value
        query += " ORDER BY seat_id"

        result = self.session.execute(text(query), params)
        return [
            Seat(
                event_id=row.event_id,
                seat_id=row.seat_id,
                category=row.category,
                price=Money(amount_centavos=row.price_centavos, currency=row.currency),
                status=SeatStatus(row.status),
            )
            for row in result
        ]

    def find_by_seats_for_update(self, event_id: str, seat_ids: list[str]) -> list[Seat]:
        """Locks selected seats ordered by seat_id strictly to eliminate deadlocks."""
        query = """
            SELECT event_id, seat_id, category, price_centavos, currency, status
            FROM seats
            WHERE event_id = :event_id AND seat_id = ANY(:seat_ids)
            ORDER BY seat_id
            FOR UPDATE
        """
        result = self.session.execute(text(query), {"event_id": event_id, "seat_ids": seat_ids})
        return [
            Seat(
                event_id=row.event_id,
                seat_id=row.seat_id,
                category=row.category,
                price=Money(amount_centavos=row.price_centavos, currency=row.currency),
                status=SeatStatus(row.status),
            )
            for row in result
        ]

    def exists_any(self, event_id: str) -> bool:
        result = self.session.execute(
            text("SELECT 1 FROM seats WHERE event_id = :event_id LIMIT 1"),
            {"event_id": event_id},
        )
        return result.first() is not None


class PostgresOrderRepository:
    """SQLAlchemy PostgreSQL implementation of OrderRepository."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def save(self, order: Order) -> None:
        self.session.execute(
            text(
                """
                INSERT INTO orders (order_id, customer_id, event_id, total_amount_centavos, currency, status)
                VALUES (:order_id, :customer_id, :event_id, :total_amount_centavos, :currency, :status)
                ON CONFLICT (order_id) DO NOTHING
                """
            ),
            {
                "order_id": order.order_id,
                "customer_id": order.customer_id,
                "event_id": order.event_id,
                "total_amount_centavos": order.total_amount.amount_centavos,
                "currency": order.total_amount.currency,
                "status": order.status.value,
            },
        )

        for t in order.tickets:
            self.session.execute(
                text(
                    """
                    INSERT INTO tickets (ticket_id, order_id, event_id, seat_id, ticket_code)
                    VALUES (:ticket_id, :order_id, :event_id, :seat_id, :ticket_code)
                    ON CONFLICT (ticket_id) DO NOTHING
                    """
                ),
                {
                    "ticket_id": t.ticket_id,
                    "order_id": t.order_id,
                    "event_id": t.event_id,
                    "seat_id": t.seat_id,
                    "ticket_code": t.code,
                },
            )

    def find_by_id(self, order_id: str) -> Order | None:
        order_query = (
            "SELECT order_id, customer_id, event_id, total_amount_centavos, currency, status "
            "FROM orders WHERE order_id = :order_id"
        )
        order_row = self.session.execute(text(order_query), {"order_id": order_id}).first()

        if not order_row:
            return None

        tickets_query = (
            "SELECT ticket_id, order_id, event_id, seat_id, ticket_code "
            "FROM tickets WHERE order_id = :order_id ORDER BY seat_id"
        )
        tickets_rows = self.session.execute(text(tickets_query), {"order_id": order_id})

        tickets = [
            Ticket(
                ticket_id=r.ticket_id,
                order_id=r.order_id,
                event_id=r.event_id,
                seat_id=r.seat_id,
                code=r.ticket_code,
            )
            for r in tickets_rows
        ]

        return Order(
            order_id=order_row.order_id,
            customer_id=order_row.customer_id,
            event_id=order_row.event_id,
            tickets=tickets,
            total_amount=Money(amount_centavos=order_row.total_amount_centavos, currency=order_row.currency),
            status=OrderStatus(order_row.status),
        )


class PostgresIdempotencyStore:
    """SQLAlchemy PostgreSQL implementation of customer-scoped IdempotencyStore."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def reserve(self, customer_id: str, key: str, request_hash: str) -> bool:
        """Reserves key with ON CONFLICT (customer_id, key) DO NOTHING. Returns True if row inserted."""
        result = self.session.execute(
            text(
                """
                INSERT INTO idempotency_keys (customer_id, key, request_hash)
                VALUES (:customer_id, :key, :request_hash)
                ON CONFLICT (customer_id, key) DO NOTHING
                RETURNING key
                """
            ),
            {"customer_id": customer_id, "key": key, "request_hash": request_hash},
        )
        return result.first() is not None

    def get(self, customer_id: str, key: str) -> StoredIdempotencyRecord | None:
        select_query = (
            "SELECT customer_id, key, request_hash, response_status, response_body "
            "FROM idempotency_keys WHERE customer_id = :customer_id AND key = :key"
        )
        row = self.session.execute(
            text(select_query),
            {"customer_id": customer_id, "key": key},
        ).first()

        if not row:
            return None

        return StoredIdempotencyRecord(
            customer_id=row.customer_id,
            key=row.key,
            request_hash=row.request_hash,
            response_status=row.response_status,
            response_body=row.response_body,
        )

    def update_response(self, customer_id: str, key: str, status: int, body: dict[str, Any]) -> None:
        import json

        self.session.execute(
            text(
                """
                UPDATE idempotency_keys
                SET response_status = :status, response_body = :body
                WHERE customer_id = :customer_id AND key = :key
                """
            ),
            {"customer_id": customer_id, "key": key, "status": status, "body": json.dumps(body)},
        )

    def remove(self, customer_id: str, key: str) -> None:
        self.session.execute(
            text("DELETE FROM idempotency_keys WHERE customer_id = :customer_id AND key = :key"),
            {"customer_id": customer_id, "key": key},
        )
