"""Unit tests of the Event aggregate (change e1-event-catalog, task 1.1; design EC-01, EC-07).

Spec catalog/event-management. The domain is pure Python, so these tests need no database or framework.
"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from catalog.domain.event import (
    Event,
    EventDetails,
    EventNotEditableError,
    EventNotPublishableError,
    EventPublished,
    EventStatus,
    EventType,
    InvalidEventError,
    Participant,
    StaleVersionError,
    TicketModality,
    Venue,
    Zone,
)

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)
NEXT_MONTH = NOW + timedelta(days=30)
OWNER = "5b0c1d2e-3f40-4a5b-8c6d-7e8f9a0b1c2d"

PLATEA = Zone(code="PLATEA", name="Platea", modality=TicketModality.NUMBERED, seat_count=3)
CAMPO = Zone(code="CAMPO", name="Campo", modality=TicketModality.UNNUMBERED, capacity=8000)


def details(**changes: object) -> EventDetails:
    values: dict[str, object] = {
        "title": "Noche de Tango en el Puerto",
        "description": "Tango de orquesta a orillas del río.",
        "type": EventType.CONCERT,
        "organizer_name": "Orquesta Típica Malvón",
        "participants": (Participant("Orquesta Típica Malvón"), Participant("Lucía Ríos")),
        "starts_at": NEXT_MONTH,
        "venue": Venue(name="Teatro del Lago", city="Rosario"),
        "zones": (PLATEA, CAMPO),
    }
    values.update(changes)
    return EventDetails(**values)  # type: ignore[arg-type]


def draft(**changes: object) -> Event:
    return Event.create(event_id=uuid4(), owner_id=OWNER, details=details(**changes), now=NOW)


def invalid_fields(**changes: object) -> set[str]:
    with pytest.raises(InvalidEventError) as error:
        details(**changes)
    return set(error.value.errors)


def test_create_gives_a_draft_at_version_one_owned_by_the_creator() -> None:
    """Req: An EVENT_OWNER or an ADMIN creates a draft event. Scenario: EVENT_OWNER creates a draft."""
    event = draft()

    assert event.status is EventStatus.DRAFT
    assert event.version == 1
    assert event.owner_id == OWNER
    assert event.created_at == NOW
    assert event.published_at is None


def test_missing_title_is_rejected() -> None:
    """Req: Event data is validated. Scenario: Missing title and unknown type."""
    assert invalid_fields(title="   ") == {"title"}


def test_every_offending_field_is_named_at_once() -> None:
    """Req: Event data is validated. Scenario: Missing title and unknown type."""
    fields = invalid_fields(title="", organizer_name="", description="x" * 5001)

    assert fields == {"title", "organizer_name", "description"}


def test_title_longer_than_200_characters_is_rejected() -> None:
    """Req: Event data is validated."""
    assert invalid_fields(title="x" * 201) == {"title"}


def test_start_without_time_zone_is_rejected() -> None:
    """Req: Event data is validated. Scenario: Start time without a time zone."""
    assert invalid_fields(starts_at=datetime(2026, 12, 20, 21, 0)) == {"starts_at"}


def test_more_than_50_participants_are_rejected() -> None:
    """Req: Event data is validated. Scenario: Too many participants."""
    participants = tuple(Participant(f"Participante {n}") for n in range(51))

    assert invalid_fields(participants=participants) == {"participants"}


def test_participant_without_name_is_rejected() -> None:
    """Req: Event data is validated."""
    assert invalid_fields(participants=(Participant(""),)) == {"participants[0].name"}


def test_venue_needs_a_name_and_a_city() -> None:
    """Req: Event data is validated."""
    assert invalid_fields(venue=Venue(name="", city="")) == {"venue.name", "venue.city"}


def test_more_than_20_zones_are_rejected() -> None:
    """Req: Event data is validated."""
    zones = tuple(
        Zone(code=f"Z{n}", name=f"Zona {n}", modality=TicketModality.UNNUMBERED, capacity=10)
        for n in range(21)
    )

    assert invalid_fields(zones=zones) == {"zones"}


def test_numbered_zone_has_deterministic_seat_ids() -> None:
    """Req: Each zone has a ticket modality. Scenario: Numbered zone."""
    assert PLATEA.seat_ids() == ("PLATEA-1", "PLATEA-2", "PLATEA-3")


def test_unnumbered_zone_has_a_capacity_and_no_seat_ids() -> None:
    """Req: Each zone has a ticket modality. Scenario: Unnumbered zone."""
    assert CAMPO.capacity == 8000
    assert CAMPO.seat_ids() == ()


def test_numbered_zone_with_a_capacity_is_rejected() -> None:
    """Req: Each zone has a ticket modality. Scenario: Numbered zone with a capacity."""
    zone = Zone(code="A", name="A", modality=TicketModality.NUMBERED, capacity=100)

    assert invalid_fields(zones=(zone,)) == {"zones[0]"}


def test_unnumbered_zone_with_a_seat_count_is_rejected() -> None:
    """Req: Each zone has a ticket modality."""
    zone = Zone(code="A", name="A", modality=TicketModality.UNNUMBERED, seat_count=10)

    assert invalid_fields(zones=(zone,)) == {"zones[0]"}


def test_zone_sizes_have_limits() -> None:
    """Req: Each zone has a ticket modality."""
    too_many_seats = Zone(code="A", name="A", modality=TicketModality.NUMBERED, seat_count=5001)
    too_large = Zone(code="B", name="B", modality=TicketModality.UNNUMBERED, capacity=50001)
    empty = Zone(code="C", name="C", modality=TicketModality.UNNUMBERED, capacity=0)

    assert invalid_fields(zones=(too_many_seats, too_large, empty)) == {"zones[0]", "zones[1]", "zones[2]"}


def test_zone_code_must_match_its_pattern() -> None:
    """Req: Each zone has a ticket modality."""
    zone = Zone(code="platea-1", name="Platea", modality=TicketModality.NUMBERED, seat_count=1)

    assert invalid_fields(zones=(zone,)) == {"zones[0].code"}


def test_repeated_zone_code_is_rejected() -> None:
    """Req: Each zone has a ticket modality. Scenario: Repeated zone code."""
    first = Zone(code="A", name="A", modality=TicketModality.NUMBERED, seat_count=1)
    second = Zone(code="A", name="Otra A", modality=TicketModality.UNNUMBERED, capacity=1)

    assert invalid_fields(zones=(first, second)) == {"zones"}


def test_draft_replaced_with_its_current_version() -> None:
    """Req: A draft is edited with its current version. Scenario: Edit with the current version."""
    event = draft()

    edited = event.replace(details(title="Tango en el Puerto"), expected_version=1)

    assert edited.details.title == "Tango en el Puerto"
    assert edited.version == 2
    assert edited.owner_id == OWNER
    assert edited.id == event.id


def test_draft_replaced_with_a_stale_version_is_refused() -> None:
    """Req: A draft is edited with its current version. Scenario: Edit with a stale version."""
    event = replace(draft(), version=2)

    with pytest.raises(StaleVersionError):
        event.replace(details(title="Otro"), expected_version=1)


def test_published_event_is_not_replaced() -> None:
    """Req: A draft is edited with its current version. Scenario: Edit of a published event."""
    published, _ = draft().publish(now=NOW)

    with pytest.raises(EventNotEditableError):
        published.replace(details(title="Otro"), expected_version=published.version)


def test_complete_draft_is_published() -> None:
    """Req: A draft is published once it is complete. Scenario: Complete draft published."""
    event = draft()

    published, domain_event = event.publish(now=NOW)

    assert published.status is EventStatus.PUBLISHED
    assert published.published_at == NOW
    assert published.version == 2
    assert domain_event == EventPublished(
        event_id=event.id, owner_id=OWNER, starts_at=NEXT_MONTH, zones=(PLATEA, CAMPO)
    )


def test_draft_without_zones_is_not_published() -> None:
    """Req: A draft is published once it is complete. Scenario: Draft without zones."""
    with pytest.raises(EventNotPublishableError) as error:
        draft(zones=()).publish(now=NOW)

    assert set(error.value.reasons) == {"zones"}


def test_draft_that_starts_in_the_past_is_not_published() -> None:
    """Req: A draft is published once it is complete. Scenario: Draft that starts in the past."""
    with pytest.raises(EventNotPublishableError) as error:
        draft(starts_at=NOW - timedelta(minutes=1), zones=()).publish(now=NOW)

    assert set(error.value.reasons) == {"zones", "starts_at"}


def test_publishing_twice_changes_nothing() -> None:
    """Req: A draft is published once it is complete. Scenario: Publishing twice."""
    published, _ = draft().publish(now=NOW)

    again, domain_event = published.publish(now=NOW + timedelta(hours=1))

    assert again == published
    assert domain_event is None
