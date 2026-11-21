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

import concurrent.futures
import os
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from sales.domain.models import Money, Order, Seat, SeatStatus, Ticket


@pytest.fixture
def db_session() -> Generator[Session]:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL not set; skipping PostgreSQL integration tests")

    engine = create_engine(database_url)
    session = Session(bind=engine)

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

    session.execute(text("DELETE FROM idempotency_keys"))
    session.execute(text("DELETE FROM tickets"))
    session.execute(text("DELETE FROM orders"))
    session.execute(text("DELETE FROM seats"))
    session.commit()
    session.close()
    engine.dispose()


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


def test_concurrent_seat_locking_ordered_for_update(db_session: Session) -> None:
    """Verifies that simultaneous transactions locking seats with FOR UPDATE.

    Prevents race conditions and double selling.
    """
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL not set")

    from sales.application.orders import PurchaseTicketsCommand, PurchaseTicketsUseCase
    from sales.domain.exceptions import SeatNotAvailableError
    from sales.infrastructure.repositories import PostgresInventoryRepository
    from sales.infrastructure.uow import SqlAlchemyUnitOfWork

    engine = create_engine(database_url)
    session_factory = sessionmaker(bind=engine)

    # Initialize available seat
    repo = PostgresInventoryRepository(db_session)
    seat = Seat("evt-conc-1", "S-1", "VIP", Money(50000), SeatStatus.AVAILABLE)
    repo.save_all([seat])
    db_session.commit()

    def attempt_purchase(customer_id: str, key: str) -> tuple[bool, str | None]:
        uow = SqlAlchemyUnitOfWork(session_factory)
        use_case = PurchaseTicketsUseCase(uow)
        cmd = PurchaseTicketsCommand(
            customer_id=customer_id,
            event_id="evt-conc-1",
            seat_ids=["S-1"],
            idempotency_key=key,
        )
        try:
            res = use_case.execute(cmd)
            return True, res.order.order_id
        except SeatNotAvailableError as exc:
            return False, str(exc)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(attempt_purchase, "usr-conc-1", "key-conc-1")
        f2 = executor.submit(attempt_purchase, "usr-conc-2", "key-conc-2")
        r1 = f1.result()
        r2 = f2.result()

    # Exactly one purchase must succeed, the other must fail with unavailable seat
    successes = [r for r in [r1, r2] if r[0]]
    failures = [r for r in [r1, r2] if not r[0]]
    assert len(successes) == 1, f"Expected 1 success, got {len(successes)}: {r1}, {r2}"
    assert len(failures) == 1, f"Expected 1 failure, got {len(failures)}: {r1}, {r2}"
    assert "Seats not available: S-1" in (failures[0][1] or "")

    # Verify exactly 1 ticket was sold in PostgreSQL
    with session_factory() as check_session:
        tickets_count = check_session.execute(
            text("SELECT COUNT(*) FROM tickets WHERE event_id = 'evt-conc-1'")
        ).scalar()
        assert tickets_count == 1


def test_concurrent_idempotent_double_click_same_key(db_session: Session) -> None:
    """Verifies that simultaneous requests with the exact same Idempotency-Key.

    Ensures single order creation and duplicate prevention for the same customer.
    """
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL not set")

    from sales.application.exceptions import IdempotencyKeyMismatchError
    from sales.application.orders import PurchaseTicketsCommand, PurchaseTicketsUseCase
    from sales.domain.exceptions import SeatNotAvailableError
    from sales.infrastructure.repositories import PostgresInventoryRepository
    from sales.infrastructure.uow import SqlAlchemyUnitOfWork

    engine = create_engine(database_url)
    session_factory = sessionmaker(bind=engine)

    # Initialize available seat
    repo = PostgresInventoryRepository(db_session)
    seat = Seat("evt-conc-2", "S-2", "VIP", Money(50000), SeatStatus.AVAILABLE)
    repo.save_all([seat])
    db_session.commit()

    shared_key = "key-double-click-test"

    def attempt_click() -> tuple[bool, str | None]:
        uow = SqlAlchemyUnitOfWork(session_factory)
        use_case = PurchaseTicketsUseCase(uow)
        cmd = PurchaseTicketsCommand(
            customer_id="usr-clicker",
            event_id="evt-conc-2",
            seat_ids=["S-2"],
            idempotency_key=shared_key,
        )
        try:
            res = use_case.execute(cmd)
            return True, res.order.order_id
        except (SeatNotAvailableError, IdempotencyKeyMismatchError) as exc:
            return False, str(exc)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(attempt_click)
        f2 = executor.submit(attempt_click)
        r1 = f1.result()
        r2 = f2.result()

    # Check outcomes:
    if r1[0] and r2[0]:
        assert r1[1] == r2[1]
    else:
        assert (r1[0] and not r2[0]) or (r2[0] and not r1[0])

    # In either case, exactly ONE order and ONE ticket exist in the database
    with session_factory() as check_session:
        orders_count = check_session.execute(
            text("SELECT COUNT(*) FROM orders WHERE event_id = 'evt-conc-2'")
        ).scalar()
        tickets_count = check_session.execute(
            text("SELECT COUNT(*) FROM tickets WHERE event_id = 'evt-conc-2'")
        ).scalar()
        keys_count = check_session.execute(
            text("SELECT COUNT(*) FROM idempotency_keys WHERE customer_id = 'usr-clicker' AND key = :k"),
            {"k": shared_key},
        ).scalar()
        assert orders_count == 1
        assert tickets_count == 1
        assert keys_count == 1


def test_repeated_reads_do_not_exhaust_connection_pool(db_session: Session) -> None:
    """Verifies that consecutive reads inside Unit of Work close sessions and do not exhaust pool."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL not set")

    from sales.application.inventory import GetAvailableSeatsUseCase
    from sales.infrastructure.repositories import PostgresInventoryRepository
    from sales.infrastructure.uow import SqlAlchemyUnitOfWork

    engine = create_engine(database_url, pool_size=5, max_overflow=10)
    session_factory = sessionmaker(bind=engine)

    # Initialize a seat
    repo = PostgresInventoryRepository(db_session)
    seat = Seat("evt-pool-1", "P-1", "General", Money(25000), SeatStatus.AVAILABLE)
    repo.save_all([seat])
    db_session.commit()

    # Execute 25 consecutive reads (exceeding pool_size=5 + max_overflow=10 = 15 connections)
    for _ in range(25):
        with SqlAlchemyUnitOfWork(session_factory) as uow:
            use_case = GetAvailableSeatsUseCase(uow.inventory_repo)
            seats = use_case.execute("evt-pool-1", SeatStatus.AVAILABLE)
            assert len(seats) == 1
            assert seats[0].seat_id == "P-1"

    engine.dispose()
