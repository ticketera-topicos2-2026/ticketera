"""Integration tests of the catalog persistence against PostgreSQL (change e1-event-catalog, task 3.3; design
EC-05, EC-06, EC-08, "Concurrency and Idempotency").

Spec catalog/event-management and catalog/event-browsing. The concurrency tests open one session per thread,
as concurrent requests do, and rely on PostgreSQL row locks.
"""

import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from catalog.application.access import AuthenticatedUser
from catalog.application.events import CatalogService
from catalog.application.exceptions import IdempotencyKeyMismatchError
from catalog.application.ports import Page, PublicFilters
from catalog.domain.event import (
    Event,
    EventDetails,
    EventStatus,
    EventType,
    Participant,
    TicketModality,
    Venue,
    Zone,
)
from catalog.infrastructure.repositories import SqlAlchemyEventRepository, SqlAlchemyIdempotencyStore
from catalog.infrastructure.uow import SqlAlchemyUnitOfWork

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)
OWNER = AuthenticatedUser(sub="owner-sub", roles=frozenset({"EVENT_OWNER"}))
ADMIN = AuthenticatedUser(sub="admin-sub", roles=frozenset({"ADMIN"}))
FIRST_PAGE = Page(limit=20, offset=0)


def details(
    title: str = "Noche de Tango", days: int = 30, event_type: EventType = EventType.CONCERT
) -> EventDetails:
    return EventDetails(
        title=title,
        description="Tango de orquesta.",
        type=event_type,
        organizer_name="Orquesta Típica Malvón",
        participants=(Participant("Orquesta Típica Malvón"), Participant("Lucía Ríos")),
        starts_at=NOW + timedelta(days=days),
        venue=Venue(name="Teatro del Lago", city="Rosario", address="Av. de la Costa 1200"),
        zones=(
            Zone(code="PLATEA", name="Platea", modality=TicketModality.NUMBERED, seat_count=320),
            Zone(code="CAMPO", name="Campo", modality=TicketModality.UNNUMBERED, capacity=2000),
        ),
    )


def new_event(owner: str = OWNER.sub, created_at: datetime = NOW, **detail_changes: object) -> Event:
    return Event.create(event_id=uuid4(), owner_id=owner, details=details(**detail_changes), now=created_at)  # type: ignore[arg-type]


def service(session_factory: sessionmaker[Session]) -> CatalogService:
    return CatalogService(
        uow_factory=lambda: SqlAlchemyUnitOfWork(session_factory), clock=lambda: NOW, new_id=uuid4
    )


def save(session_factory: sessionmaker[Session], *events: Event) -> None:
    with session_factory() as session:
        repository = SqlAlchemyEventRepository(session)
        for event in events:
            repository.add(event)
        session.commit()


def test_event_round_trip_keeps_every_field(session_factory: sessionmaker[Session]) -> None:
    """Design EC-08: an event is stored with its zones and participants in order, and loaded back equal."""
    event = new_event()
    save(session_factory, event)

    with session_factory() as session:
        loaded = SqlAlchemyEventRepository(session).get(event.id)

    assert loaded == event


def test_conditional_update_applies_only_to_the_expected_draft_version(
    session_factory: sessionmaker[Session],
) -> None:
    """Req: A draft is edited with its current version. Scenarios: Edit with the current version; Edit with a
    stale version."""
    event = new_event()
    save(session_factory, event)
    edited = event.replace(details(title="Tango en el Puerto"), expected_version=1)

    with session_factory() as session:
        repository = SqlAlchemyEventRepository(session)
        assert repository.update(edited, expected_version=1) is True
        assert repository.update(edited, expected_version=1) is False
        session.commit()
        stored = repository.get(event.id)

    assert stored is not None
    assert (stored.version, stored.details.title) == (2, "Tango en el Puerto")


def test_published_event_is_never_updated(session_factory: sessionmaker[Session]) -> None:
    """Req: A draft is edited with its current version. Scenario: Edit of a published event."""
    event = new_event()
    published, _ = event.publish(now=NOW)
    save(session_factory, published)

    with session_factory() as session:
        stale_edit = replace(published, details=details(title="Otro"), version=published.version + 1)
        assert (
            SqlAlchemyEventRepository(session).update(stale_edit, expected_version=published.version) is False
        )


def run_concurrently(*actions: Callable[[], object]) -> list[object]:
    with ThreadPoolExecutor(max_workers=len(actions)) as pool:
        return [future.result() for future in [pool.submit(action) for action in actions]]


def test_two_concurrent_edits_of_the_same_version(session_factory: sessionmaker[Session]) -> None:
    """Req: A draft is edited with its current version. Scenario: Two concurrent edits of the same version."""
    event = new_event()
    save(session_factory, event)
    catalog = service(session_factory)
    barrier = threading.Barrier(2)

    def edit(user: AuthenticatedUser, title: str) -> str:
        barrier.wait()
        try:
            catalog.replace_event(user, event.id, details(title=title), expected_version=1)
        except Exception as error:  # noqa: BLE001 - the outcome under test is the exception type
            return type(error).__name__
        return "ok"

    outcomes = run_concurrently(lambda: edit(OWNER, "Del dueño"), lambda: edit(ADMIN, "Del admin"))

    assert sorted(outcomes) == ["StaleVersionError", "ok"]  # type: ignore[type-var]
    stored = catalog.get_managed_event(ADMIN, event.id)
    assert stored.version == 2


def test_publish_and_edit_at_the_same_time_never_edit_a_published_event(
    session_factory: sessionmaker[Session],
) -> None:
    """Req: A draft is published once it is complete. Scenario: Publish and edit at the same time."""
    event = new_event()
    save(session_factory, event)
    locked = threading.Event()

    def publish_slowly() -> None:
        with session_factory() as session:
            repository = SqlAlchemyEventRepository(session)
            current = repository.get_for_update(event.id)
            assert current is not None
            locked.set()
            time.sleep(0.5)
            published, _ = current.publish(now=NOW)
            repository.update(published, expected_version=current.version)
            session.commit()

    def edit_while_locked() -> bool:
        locked.wait(timeout=5)
        with session_factory() as session:
            edited = event.replace(details(title="Tarde"), expected_version=1)
            updated = SqlAlchemyEventRepository(session).update(edited, expected_version=1)
            session.commit()
            return updated

    _, edit_applied = run_concurrently(publish_slowly, edit_while_locked)

    assert edit_applied is False
    stored = service(session_factory).get_published_event(event.id)
    assert (stored.status, stored.details.title) == (EventStatus.PUBLISHED, "Noche de Tango")


def test_public_query_filters_orders_and_paginates(session_factory: sessionmaker[Session]) -> None:
    """Req: The public catalog is filtered and paginated.

    Scenarios: Filter by type and date range; Second page. Also Req: The public catalog lists only
    published events. Scenario: Draft not listed.
    """
    published = [new_event(title=f"C{days}", days=days).publish(now=NOW)[0] for days in (40, 10, 20)]
    play, _ = new_event(title="Obra", days=15, event_type=EventType.THEATER).publish(now=NOW)
    past, _ = new_event(title="Pasado", days=1).publish(now=NOW)
    draft = new_event(title="Borrador", days=5)
    save(session_factory, *published, play, past, draft)
    later_now = NOW + timedelta(days=2)

    with session_factory() as session:
        repository = SqlAlchemyEventRepository(session)
        everything = repository.list_published(PublicFilters(), now=later_now, page=FIRST_PAGE)
        concerts = repository.list_published(
            PublicFilters(type=EventType.CONCERT), now=later_now, page=FIRST_PAGE
        )
        window = repository.list_published(
            PublicFilters(starts_from=NOW + timedelta(days=12), starts_to=NOW + timedelta(days=25)),
            now=later_now,
            page=FIRST_PAGE,
        )
        second_page = repository.list_published(PublicFilters(), now=later_now, page=Page(limit=2, offset=2))

    assert [event.details.title for event in everything.items] == ["C10", "Obra", "C20", "C40"]
    assert everything.total == 4
    assert [event.details.title for event in concerts.items] == ["C10", "C20", "C40"]
    assert [event.details.title for event in window.items] == ["Obra", "C20"]
    assert [event.details.title for event in second_page.items] == ["C20", "C40"]


def test_managed_query_scopes_by_owner_newest_first(session_factory: sessionmaker[Session]) -> None:
    """Req: Managers list the events they can manage. Scenarios: EVENT_OWNER lists their events; ADMIN lists
    every event."""
    older = new_event(title="Viejo", created_at=NOW - timedelta(hours=2))
    newer = new_event(title="Nuevo", created_at=NOW - timedelta(hours=1))
    other = new_event(owner="other-sub", title="Ajeno")
    save(session_factory, older, newer, other)

    with session_factory() as session:
        repository = SqlAlchemyEventRepository(session)
        mine = repository.list_managed(owner_id=OWNER.sub, page=FIRST_PAGE)
        everyone = repository.list_managed(owner_id=None, page=FIRST_PAGE)

    assert [event.details.title for event in mine.items] == ["Nuevo", "Viejo"]
    assert everyone.total == 3


def test_reserve_returns_the_committed_record_of_a_used_key(session_factory: sessionmaker[Session]) -> None:
    """Design EC-05: the first reservation inserts the key; a later one gets the stored hash and event."""
    key, event_id = uuid4(), uuid4()
    with session_factory() as session:
        store = SqlAlchemyIdempotencyStore(session)
        assert store.reserve(OWNER.sub, key, "hash") is None
        store.complete(OWNER.sub, key, event_id)
        session.commit()

    with session_factory() as session:
        record = SqlAlchemyIdempotencyStore(session).reserve(OWNER.sub, key, "hash")

    assert record is not None
    assert (record.request_hash, record.event_id) == ("hash", event_id)


def test_retry_with_the_same_key_creates_one_event(session_factory: sessionmaker[Session]) -> None:
    """Req: Event creation is idempotent. Scenario: Retry after a network timeout."""
    catalog = service(session_factory)
    key = uuid4()

    first = catalog.create_event(OWNER, details(), idempotency_key=key, request_hash="h")
    second = catalog.create_event(OWNER, details(), idempotency_key=key, request_hash="h")

    assert second.id == first.id
    assert catalog.list_managed(OWNER, FIRST_PAGE).total == 1


def test_same_key_with_a_different_body_is_rejected(session_factory: sessionmaker[Session]) -> None:
    """Req: Event creation is idempotent. Scenario: Same key with a different body."""
    catalog = service(session_factory)
    key = uuid4()
    catalog.create_event(OWNER, details(), idempotency_key=key, request_hash="h1")

    with pytest.raises(IdempotencyKeyMismatchError):
        catalog.create_event(OWNER, details(title="Otro"), idempotency_key=key, request_hash="h2")

    assert catalog.list_managed(OWNER, FIRST_PAGE).total == 1


def test_two_users_with_the_same_key_create_two_events(session_factory: sessionmaker[Session]) -> None:
    """Req: Event creation is idempotent. Scenario: Two users with the same key."""
    catalog = service(session_factory)
    key = uuid4()

    catalog.create_event(OWNER, details(), idempotency_key=key, request_hash="h")
    catalog.create_event(ADMIN, details(), idempotency_key=key, request_hash="h")

    assert catalog.list_managed(ADMIN, FIRST_PAGE).total == 2


def test_concurrent_requests_with_the_same_key_create_one_event(
    session_factory: sessionmaker[Session],
) -> None:
    """Req: Event creation is idempotent. Scenario: Concurrent requests with the same key."""
    catalog = service(session_factory)
    key = uuid4()
    barrier = threading.Barrier(10)

    def create() -> UUID:
        barrier.wait()
        return catalog.create_event(OWNER, details(), idempotency_key=key, request_hash="h").id

    ids = run_concurrently(*([create] * 10))

    assert len(set(ids)) == 1
    assert catalog.list_managed(OWNER, FIRST_PAGE).total == 1


def test_failed_creation_leaves_no_key(session_factory: sessionmaker[Session]) -> None:
    """Design EC-05: a failed transaction removes its key, so a retry runs normally."""
    key = uuid4()
    with session_factory() as session:
        SqlAlchemyIdempotencyStore(session).reserve(OWNER.sub, key, "h")
        session.rollback()

    with session_factory() as session:
        remaining = session.execute(text("SELECT count(*) FROM idempotency_keys")).scalar_one()

    assert remaining == 0
