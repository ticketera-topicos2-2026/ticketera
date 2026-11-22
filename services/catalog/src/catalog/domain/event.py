"""The Event aggregate of the catalog (change e1-event-catalog; design EC-01, EC-07, EC-13).

Pure Python, with no framework or database import (D-33). An event describes an offer: its zones say
how tickets are sold (numbered seats or unnumbered capacity, DF-02), but prices, availability and
selling belong to `sales` (D-28).
"""

import re
from dataclasses import dataclass, field
from dataclasses import replace as copy_with
from datetime import datetime
from enum import StrEnum
from typing import Self
from uuid import UUID

MAX_TITLE_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 5000
MAX_NAME_LENGTH = 200
MAX_PARTICIPANTS = 50
MAX_ZONES = 20
MAX_SEATS_PER_ZONE = 5000
MAX_ZONE_CAPACITY = 50000
ZONE_CODE_PATTERN = re.compile(r"[A-Z0-9]{1,8}")


class EventType(StrEnum):
    CONCERT = "CONCERT"
    THEATER = "THEATER"
    SPORTS = "SPORTS"
    CONFERENCE = "CONFERENCE"
    FESTIVAL = "FESTIVAL"
    OTHER = "OTHER"


class TicketModality(StrEnum):
    NUMBERED = "NUMBERED"
    UNNUMBERED = "UNNUMBERED"


class EventStatus(StrEnum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"


class InvalidEventError(Exception):
    """The event data breaks a rule; `errors` maps each offending field to the reason."""

    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__(", ".join(f"{name}: {reason}" for name, reason in errors.items()))
        self.errors = errors


class StaleVersionError(Exception):
    """The draft changed since the version the client read."""


class EventNotEditableError(Exception):
    """Only a draft can be replaced; a published event is not editable in Stage I."""


class EventNotPublishableError(Exception):
    """The draft is incomplete; `reasons` maps each missing condition to the reason."""

    def __init__(self, reasons: dict[str, str]) -> None:
        super().__init__(", ".join(f"{name}: {reason}" for name, reason in reasons.items()))
        self.reasons = reasons


@dataclass(frozen=True)
class Venue:
    name: str
    city: str
    address: str | None = None


@dataclass(frozen=True)
class Participant:
    """Someone who performs at the event (S-03): an artist, a speaker or a team."""

    name: str


@dataclass(frozen=True)
class Zone:
    code: str
    name: str
    modality: TicketModality
    seat_count: int | None = None
    capacity: int | None = None

    def seat_ids(self) -> tuple[str, ...]:
        """The seat ids of a numbered zone, `<code>-1` to `<code>-<seat count>` (EC-07); none otherwise."""
        if self.modality is not TicketModality.NUMBERED or self.seat_count is None:
            return ()
        return tuple(f"{self.code}-{number}" for number in range(1, self.seat_count + 1))


@dataclass(frozen=True)
class EventDetails:
    """Everything the owner of an event chooses; validated as a whole, naming every offending field."""

    title: str
    description: str
    type: EventType
    organizer_name: str
    participants: tuple[Participant, ...]
    starts_at: datetime
    venue: Venue
    zones: tuple[Zone, ...]

    def __post_init__(self) -> None:
        errors = _details_errors(self)
        if errors:
            raise InvalidEventError(errors)


@dataclass(frozen=True)
class EventPublished:
    """Domain event raised when a draft is published; from Stage II, the integration event of EC-13."""

    event_id: UUID
    owner_id: str
    starts_at: datetime
    zones: tuple[Zone, ...]


@dataclass(frozen=True)
class Event:
    """Aggregate root. Only a draft changes, and every change increments its version (EC-06)."""

    id: UUID
    owner_id: str
    details: EventDetails
    status: EventStatus
    version: int
    created_at: datetime
    published_at: datetime | None = field(default=None)

    @classmethod
    def create(cls, event_id: UUID, owner_id: str, details: EventDetails, now: datetime) -> Self:
        return cls(
            id=event_id,
            owner_id=owner_id,
            details=details,
            status=EventStatus.DRAFT,
            version=1,
            created_at=now,
        )

    def replace(self, details: EventDetails, expected_version: int) -> "Event":
        if self.status is not EventStatus.DRAFT:
            raise EventNotEditableError(f"event {self.id} is {self.status}")
        if expected_version != self.version:
            raise StaleVersionError(f"event {self.id} is at version {self.version}, not {expected_version}")
        return copy_with(self, details=details, version=self.version + 1)

    def publish(self, now: datetime) -> tuple["Event", EventPublished | None]:
        """Publishes a complete draft; a published event is returned unchanged, with no domain event."""
        if self.status is EventStatus.PUBLISHED:
            return self, None
        reasons: dict[str, str] = {}
        if not self.details.zones:
            reasons["zones"] = "at least one zone is required"
        if self.details.starts_at <= now:
            reasons["starts_at"] = "the event must start in the future"
        if reasons:
            raise EventNotPublishableError(reasons)
        published = copy_with(self, status=EventStatus.PUBLISHED, published_at=now, version=self.version + 1)
        return published, EventPublished(
            event_id=self.id,
            owner_id=self.owner_id,
            starts_at=self.details.starts_at,
            zones=self.details.zones,
        )


def _text_error(value: str, max_length: int, *, required: bool = True) -> str | None:
    if required and not value.strip():
        return "is required"
    if len(value) > max_length:
        return f"must have at most {max_length} characters"
    return None


def _details_errors(details: EventDetails) -> dict[str, str]:
    errors: dict[str, str] = {}
    checks = {
        "title": _text_error(details.title, MAX_TITLE_LENGTH),
        "description": _text_error(details.description, MAX_DESCRIPTION_LENGTH, required=False),
        "organizer_name": _text_error(details.organizer_name, MAX_NAME_LENGTH),
        "venue.name": _text_error(details.venue.name, MAX_NAME_LENGTH),
        "venue.city": _text_error(details.venue.city, MAX_NAME_LENGTH),
    }
    errors.update({name: reason for name, reason in checks.items() if reason})
    if not isinstance(details.type, EventType):
        errors["type"] = "is not a known event type"
    if details.starts_at.tzinfo is None or details.starts_at.utcoffset() is None:
        errors["starts_at"] = "must include a time zone offset"
    errors.update(_participants_errors(details.participants))
    errors.update(_zones_errors(details.zones))
    return errors


def _participants_errors(participants: tuple[Participant, ...]) -> dict[str, str]:
    if len(participants) > MAX_PARTICIPANTS:
        return {"participants": f"at most {MAX_PARTICIPANTS} participants are allowed"}
    errors: dict[str, str] = {}
    for index, participant in enumerate(participants):
        reason = _text_error(participant.name, MAX_NAME_LENGTH)
        if reason:
            errors[f"participants[{index}].name"] = reason
    return errors


def _zones_errors(zones: tuple[Zone, ...]) -> dict[str, str]:
    if len(zones) > MAX_ZONES:
        return {"zones": f"at most {MAX_ZONES} zones are allowed"}
    errors: dict[str, str] = {}
    for index, zone in enumerate(zones):
        errors.update({f"zones[{index}]{suffix}": reason for suffix, reason in _zone_errors(zone).items()})
    codes = [zone.code for zone in zones]
    repeated = sorted({code for code in codes if codes.count(code) > 1})
    if repeated:
        errors["zones"] = f"zone codes must be unique; repeated: {', '.join(repeated)}"
    return errors


def _zone_errors(zone: Zone) -> dict[str, str]:
    errors: dict[str, str] = {}
    if not ZONE_CODE_PATTERN.fullmatch(zone.code):
        errors[".code"] = "must be 1 to 8 uppercase letters or digits"
    name_reason = _text_error(zone.name, MAX_NAME_LENGTH)
    if name_reason:
        errors[".name"] = name_reason
    modality_reason = _modality_error(zone)
    if modality_reason:
        errors[""] = modality_reason
    return errors


def _modality_error(zone: Zone) -> str | None:
    if zone.modality is TicketModality.NUMBERED:
        if zone.capacity is not None or zone.seat_count is None:
            return "a numbered zone has a seat count and no capacity"
        if not 1 <= zone.seat_count <= MAX_SEATS_PER_ZONE:
            return f"a numbered zone has from 1 to {MAX_SEATS_PER_ZONE} seats"
        return None
    if zone.seat_count is not None or zone.capacity is None:
        return "an unnumbered zone has a capacity and no seat count"
    if not 1 <= zone.capacity <= MAX_ZONE_CAPACITY:
        return f"an unnumbered zone has a capacity from 1 to {MAX_ZONE_CAPACITY}"
    return None
