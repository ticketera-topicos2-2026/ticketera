"""Unit tests of the catalog use cases with in-memory fakes (change e1-event-catalog, task 2.1; design EC-04,
EC-05, EC-06).

Spec catalog/event-management and catalog/event-browsing. The use cases get the user as a value (its `sub` and
platform roles), never a token.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from catalog.application.access import AuthenticatedUser
from catalog.application.events import CatalogService
from catalog.application.exceptions import EventNotFoundError, IdempotencyKeyMismatchError, NotAllowedError
from catalog.application.ports import Page, PublicFilters
from catalog.domain.event import (
    EventDetails,
    EventNotEditableError,
    EventStatus,
    EventType,
    Participant,
    StaleVersionError,
    TicketModality,
    Venue,
    Zone,
)
from tests.unit.fakes import FakeUnitOfWork

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)
OWNER = AuthenticatedUser(sub="owner-sub", roles=frozenset({"EVENT_OWNER"}))
OTHER_OWNER = AuthenticatedUser(sub="other-owner-sub", roles=frozenset({"EVENT_OWNER"}))
ADMIN = AuthenticatedUser(sub="admin-sub", roles=frozenset({"ADMIN"}))
CLIENT = AuthenticatedUser(sub="client-sub", roles=frozenset({"CLIENT"}))
FIRST_PAGE = Page(limit=20, offset=0)
NO_FILTERS = PublicFilters()


def details(title: str = "Noche de Tango", days: int = 30, event_type: EventType = EventType.CONCERT) -> EventDetails:
    return EventDetails(
        title=title,
        description="",
        type=event_type,
        organizer_name="Orquesta Típica Malvón",
        participants=(Participant("Lucía Ríos"),),
        starts_at=NOW + timedelta(days=days),
        venue=Venue(name="Teatro del Lago", city="Rosario"),
        zones=(Zone(code="PLATEA", name="Platea", modality=TicketModality.NUMBERED, seat_count=3),),
    )


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def service(uow: FakeUnitOfWork) -> CatalogService:
    return CatalogService(uow_factory=lambda: uow, clock=lambda: NOW, new_id=uuid4)


def create(service: CatalogService, user: AuthenticatedUser = OWNER, title: str = "Noche de Tango") -> UUID:
    return service.create_event(user, details(title=title), idempotency_key=uuid4(), request_hash=title).id


def test_event_owner_creates_a_draft_owned_by_them(service: CatalogService, uow: FakeUnitOfWork) -> None:
    """Req: An EVENT_OWNER or an ADMIN creates a draft event. Scenario: EVENT_OWNER creates a draft."""
    event = service.create_event(OWNER, details(), idempotency_key=uuid4(), request_hash="h")

    assert event.status is EventStatus.DRAFT
    assert event.owner_id == OWNER.sub
    assert uow.events.get(event.id) == event
    assert uow.commits == 1


def test_admin_creates_a_draft(service: CatalogService) -> None:
    """Req: An EVENT_OWNER or an ADMIN creates a draft event. Scenario: ADMIN creates a draft."""
    event = service.create_event(ADMIN, details(), idempotency_key=uuid4(), request_hash="h")

    assert event.owner_id == ADMIN.sub


def test_client_cannot_create_an_event(service: CatalogService, uow: FakeUnitOfWork) -> None:
    """Req: An EVENT_OWNER or an ADMIN creates a draft event. Scenario: CLIENT tries to create an event."""
    with pytest.raises(NotAllowedError):
        service.create_event(CLIENT, details(), idempotency_key=uuid4(), request_hash="h")

    assert uow.events.events == {}


def test_retry_with_the_same_key_returns_the_same_event(service: CatalogService, uow: FakeUnitOfWork) -> None:
    """Req: Event creation is idempotent. Scenario: Retry after a network timeout."""
    key = uuid4()

    first = service.create_event(OWNER, details(), idempotency_key=key, request_hash="h")
    second = service.create_event(OWNER, details(), idempotency_key=key, request_hash="h")

    assert second.id == first.id
    assert len(uow.events.events) == 1


def test_same_key_with_a_different_body_is_rejected(service: CatalogService, uow: FakeUnitOfWork) -> None:
    """Req: Event creation is idempotent. Scenario: Same key with a different body."""
    key = uuid4()
    service.create_event(OWNER, details(), idempotency_key=key, request_hash="h1")

    with pytest.raises(IdempotencyKeyMismatchError):
        service.create_event(OWNER, details(title="Otro"), idempotency_key=key, request_hash="h2")

    assert len(uow.events.events) == 1


def test_two_users_with_the_same_key_create_two_events(service: CatalogService) -> None:
    """Req: Event creation is idempotent. Scenario: Two users with the same key."""
    key = uuid4()

    mine = service.create_event(OWNER, details(), idempotency_key=key, request_hash="h")
    theirs = service.create_event(ADMIN, details(), idempotency_key=key, request_hash="h")

    assert mine.id != theirs.id
    assert (mine.owner_id, theirs.owner_id) == (OWNER.sub, ADMIN.sub)


def test_owner_replaces_their_draft(service: CatalogService) -> None:
    """Req: A draft is edited with its current version. Scenario: Edit with the current version."""
    event_id = create(service)

    edited = service.replace_event(OWNER, event_id, details(title="Tango en el Puerto"), expected_version=1)

    assert edited.details.title == "Tango en el Puerto"
    assert edited.version == 2


def test_stale_version_is_refused(service: CatalogService) -> None:
    """Req: A draft is edited with its current version. Scenario: Edit with a stale version."""
    event_id = create(service)
    service.replace_event(OWNER, event_id, details(title="v2"), expected_version=1)

    with pytest.raises(StaleVersionError):
        service.replace_event(ADMIN, event_id, details(title="v3"), expected_version=1)


def test_published_event_is_not_replaced(service: CatalogService) -> None:
    """Req: A draft is edited with its current version. Scenario: Edit of a published event."""
    event_id = create(service)
    published = service.publish_event(OWNER, event_id)

    with pytest.raises(EventNotEditableError):
        service.replace_event(OWNER, event_id, details(title="Otro"), expected_version=published.version)


def test_owner_publishes_their_draft(service: CatalogService) -> None:
    """Req: A draft is published once it is complete. Scenario: Complete draft published."""
    event_id = create(service)

    published = service.publish_event(OWNER, event_id)

    assert published.status is EventStatus.PUBLISHED
    assert published.published_at == NOW
    assert [event.id for event in service.list_published(NO_FILTERS, FIRST_PAGE).items] == [event_id]


def test_publishing_twice_returns_the_same_publication(service: CatalogService) -> None:
    """Req: A draft is published once it is complete. Scenario: Publishing twice."""
    event_id = create(service)
    first = service.publish_event(OWNER, event_id)

    second = service.publish_event(OWNER, event_id)

    assert second == first


def test_event_owner_cannot_read_another_owners_draft(service: CatalogService) -> None:
    """Req: An EVENT_OWNER manages only their own events. Scenario: EVENT_OWNER reads another owner's draft."""
    event_id = create(service, user=ADMIN)

    with pytest.raises(EventNotFoundError):
        service.get_managed_event(OWNER, event_id)


def test_event_owner_cannot_publish_another_owners_draft(service: CatalogService, uow: FakeUnitOfWork) -> None:
    """Req: An EVENT_OWNER manages only their own events. Scenario: EVENT_OWNER publishes another owner's draft."""
    event_id = create(service, user=OTHER_OWNER)

    with pytest.raises(EventNotFoundError):
        service.publish_event(OWNER, event_id)

    event = uow.events.get(event_id)
    assert event is not None
    assert event.status is EventStatus.DRAFT


def test_event_owner_cannot_edit_another_owners_draft(service: CatalogService) -> None:
    """Req: An EVENT_OWNER manages only their own events."""
    event_id = create(service, user=OTHER_OWNER)

    with pytest.raises(EventNotFoundError):
        service.replace_event(OWNER, event_id, details(title="Otro"), expected_version=1)


def test_admin_edits_an_owners_draft_without_taking_it(service: CatalogService) -> None:
    """Req: An EVENT_OWNER manages only their own events. Scenario: ADMIN edits an EVENT_OWNER's draft."""
    event_id = create(service)

    edited = service.replace_event(ADMIN, event_id, details(title="Corregido"), expected_version=1)

    assert edited.owner_id == OWNER.sub


def test_unknown_event_is_not_found(service: CatalogService) -> None:
    """Req: An EVENT_OWNER manages only their own events. Scenario: EVENT_OWNER reads another owner's draft."""
    with pytest.raises(EventNotFoundError):
        service.get_managed_event(ADMIN, uuid4())


def test_client_cannot_manage_events(service: CatalogService) -> None:
    """Req: Services authorize by role. Scenario: CLIENT calls an ADMIN-only endpoint."""
    event_id = create(service)

    for action in (
        lambda: service.get_managed_event(CLIENT, event_id),
        lambda: service.list_managed(CLIENT, FIRST_PAGE),
        lambda: service.publish_event(CLIENT, event_id),
        lambda: service.replace_event(CLIENT, event_id, details(), expected_version=1),
    ):
        with pytest.raises(NotAllowedError):
            action()


def test_event_owner_lists_only_their_events(service: CatalogService) -> None:
    """Req: Managers list the events they can manage. Scenario: EVENT_OWNER lists their events."""
    mine = {create(service, title="Mío 1"), create(service, title="Mío 2")}
    service.publish_event(OWNER, next(iter(mine)))
    create(service, user=OTHER_OWNER, title="Ajeno")

    result = service.list_managed(OWNER, FIRST_PAGE)

    assert {event.id for event in result.items} == mine
    assert result.total == 2


def test_admin_lists_every_event(service: CatalogService) -> None:
    """Req: Managers list the events they can manage. Scenario: ADMIN lists every event."""
    create(service)
    create(service, user=OTHER_OWNER)

    assert service.list_managed(ADMIN, FIRST_PAGE).total == 2


def test_public_list_shows_only_published_upcoming_events(service: CatalogService, uow: FakeUnitOfWork) -> None:
    """Req: The public catalog lists only published events. Scenarios: Visitor without a token; Draft not listed."""
    later = create(service, title="Después")
    service.publish_event(OWNER, later)
    sooner_id = service.create_event(
        OWNER, details(title="Antes", days=10), idempotency_key=uuid4(), request_hash="antes"
    ).id
    service.publish_event(OWNER, sooner_id)
    create(service, title="Borrador")

    items = service.list_published(NO_FILTERS, FIRST_PAGE).items

    assert [event.id for event in items] == [sooner_id, later]


def test_public_detail_hides_drafts(service: CatalogService) -> None:
    """Req: The public catalog shows a published event. Scenario: Draft requested by its identifier."""
    event_id = create(service)

    with pytest.raises(EventNotFoundError):
        service.get_published_event(event_id)

    service.publish_event(OWNER, event_id)
    assert service.get_published_event(event_id).id == event_id


def test_public_list_filters_by_type(service: CatalogService) -> None:
    """Req: The public catalog is filtered and paginated. Scenario: Filter by type and date range."""
    concert = create(service, title="Concierto")
    service.publish_event(OWNER, concert)
    play_id = service.create_event(
        OWNER, details(title="Obra", event_type=EventType.THEATER), idempotency_key=uuid4(), request_hash="obra"
    ).id
    service.publish_event(OWNER, play_id)

    items = service.list_published(PublicFilters(type=EventType.THEATER), FIRST_PAGE).items

    assert [event.id for event in items] == [play_id]
