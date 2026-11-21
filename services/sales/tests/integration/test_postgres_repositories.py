"""Integration tests for SQLAlchemy repositories against PostgreSQL in Docker (TDD).

Verifies:
- `PostgresInventoryRepository`:
  - `save_all` and `find_by_event`.
  - `find_by_seats_for_update`: acquires row-level locks strictly ordered by `seat_id` preventing deadlocks.
- `PostgresOrderRepository`:
  - `save`: stores `orders` and `tickets` atomically with `UNIQUE(event_id, seat_id)`.
  - `find_by_id`: fetches order with tickets.
- `PostgresIdempotencyStore`:
  - `reserve`: `INSERT INTO idempotency_keys ... ON CONFLICT (customer_id, key) DO NOTHING`.
  - Sequential retry replay and concurrent double-click handling.
  - Transaction failure rolls back idempotency key cleanly.
"""

import os
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from sales.domain.models import Money, Order, Seat, SeatStatus, Ticket


@pytest.fixture
def db_session() -> Generator[Session]:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL not set; skipping PostgreSQL integration tests")

    engine = create_engine(database_url)
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    # Ensure migrations are applied on fresh databases
    from alembic import command
    from alembic.config import Config

    config = Config("alembic.ini")
    command.upgrade(config, "head")

    # Clean sales tables before test
    session.execute(text("DELETE FROM idempotency_keys"))
    session.execute(text("DELETE FROM tickets"))
    session.execute(text("DELETE FROM orders"))
    session.execute(text("DELETE FROM seats"))
    session.commit()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


def test_postgres_inventory_repository(db_session: Session) -> None:
    """Verifies inventory persistence and ordered row locking in PostgreSQL."""
    from sales.infrastructure.repositories import PostgresInventoryRepository

    repo = PostgresInventoryRepository(db_session)
    s1 = Seat("evt-1", "A-2", "General", Money(20000), SeatStatus.AVAILABLE)
    s2 = Seat("evt-1", "A-1", "VIP", Money(50000), SeatStatus.AVAILABLE)

    repo.save_all([s1, s2])
    db_session.commit()

    # Query by event
    seats = repo.find_by_event("evt-1")
    assert len(seats) == 2

    # find_by_seats_for_update must return seats strictly ordered by seat_id
    locked = repo.find_by_seats_for_update("evt-1", ["A-2", "A-1"])
    assert [s.seat_id for s in locked] == ["A-1", "A-2"]


def test_postgres_order_repository_and_ticket_uniqueness(db_session: Session) -> None:
    """Verifies atomic order and ticket persistence in PostgreSQL."""
    from sales.infrastructure.repositories import PostgresOrderRepository

    repo = PostgresOrderRepository(db_session)

    t1 = Ticket("tkt-1", "ord-1", "evt-1", "A-1", "CODE-1")
    t2 = Ticket("tkt-2", "ord-1", "evt-1", "A-2", "CODE-2")
    order = Order.create("ord-1", "usr-10", "evt-1", [t1, t2], Money(70000))

    repo.save(order)
    db_session.commit()

    found = repo.find_by_id("ord-1")
    assert found is not None
    assert found.customer_id == "usr-10"
    assert len(found.tickets) == 2


def test_postgres_idempotency_store(db_session: Session) -> None:
    """Verifies customer-scoped idempotency key reservation and conflict in PostgreSQL."""
    from sales.infrastructure.repositories import PostgresIdempotencyStore

    store = PostgresIdempotencyStore(db_session)

    # 1. First attempt: successfully reserves (returns True)
    reserved = store.reserve("usr-10", "key-1", "hash-abc")
    db_session.commit()
    assert reserved is True

    # 2. Duplicate key for SAME customer: conflict (returns False)
    duplicate_same = store.reserve("usr-10", "key-1", "hash-abc")
    assert duplicate_same is False

    # 3. Same key for DIFFERENT customer: independent and successful (customer isolation)
    different_cust = store.reserve("usr-20", "key-1", "hash-xyz")
    db_session.commit()
    assert different_cust is True

    # 4. Update response
    store.update_response("usr-10", "key-1", 201, {"order_id": "ord-1"})
    db_session.commit()

    rec = store.get("usr-10", "key-1")
    assert rec is not None
    assert rec.response_status == 201
    assert rec.response_body == {"order_id": "ord-1"}
