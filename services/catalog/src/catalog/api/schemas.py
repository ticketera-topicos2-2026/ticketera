"""Request and response schemas of the catalog API (change e1-event-catalog; design EC-09, EC-10, EC-12).

Requests forbid any field outside the contract (EC-10); the domain checks the rest of the rules.
Responses are built from the aggregate: the public ones never carry the owner (spec catalog/event-browsing:
Owner not shown), and only the single-event responses carry the seat ids of numbered zones.
"""

from datetime import UTC, datetime
from typing import Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

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


class ParticipantInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str


class VenueInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    city: str
    address: str | None = None


class ZoneInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(pattern=r"^[A-Z0-9]{1,8}$")
    name: str
    modality: TicketModality
    seat_count: int | None = None
    capacity: int | None = None


class EventInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str = ""
    type: EventType
    organizer_name: str
    participants: list[ParticipantInput] = Field(default_factory=list)
    starts_at: AwareDatetime
    venue: VenueInput
    zones: list[ZoneInput] = Field(default_factory=list)

    def to_details(self) -> EventDetails:
        """The domain value; raises InvalidEventError for the rules the schema does not check."""
        return EventDetails(
            title=self.title,
            description=self.description,
            type=self.type,
            organizer_name=self.organizer_name,
            participants=tuple(Participant(participant.name) for participant in self.participants),
            starts_at=self.starts_at,
            venue=Venue(name=self.venue.name, city=self.venue.city, address=self.venue.address),
            zones=tuple(
                Zone(
                    code=zone.code,
                    name=zone.name,
                    modality=zone.modality,
                    seat_count=zone.seat_count,
                    capacity=zone.capacity,
                )
                for zone in self.zones
            ),
        )


class EventReplacement(EventInput):
    version: int = Field(ge=1)


class ParticipantOut(BaseModel):
    name: str


class VenueOut(BaseModel):
    name: str
    city: str
    address: str | None


class ZoneSummary(BaseModel):
    code: str
    name: str
    modality: TicketModality
    seat_count: int | None
    capacity: int | None

    @classmethod
    def of(cls, zone: Zone) -> Self:
        return cls(
            code=zone.code,
            name=zone.name,
            modality=zone.modality,
            seat_count=zone.seat_count,
            capacity=zone.capacity,
        )


class ZoneDetail(ZoneSummary):
    seat_ids: list[str]

    @classmethod
    def of(cls, zone: Zone) -> Self:
        return cls(**ZoneSummary.of(zone).model_dump(), seat_ids=list(zone.seat_ids()))


def _utc(moment: datetime | None) -> datetime | None:
    return moment.astimezone(UTC) if moment is not None else None


def _common_fields(event: Event) -> dict[str, object]:
    details = event.details
    return {
        "id": event.id,
        "title": details.title,
        "description": details.description,
        "type": details.type,
        "organizer_name": details.organizer_name,
        "participants": [ParticipantOut(name=participant.name) for participant in details.participants],
        "starts_at": _utc(details.starts_at),
        "venue": VenueOut(name=details.venue.name, city=details.venue.city, address=details.venue.address),
        "published_at": _utc(event.published_at),
    }


def _managed_fields(event: Event) -> dict[str, object]:
    return {
        **_common_fields(event),
        "owner_id": event.owner_id,
        "status": event.status,
        "version": event.version,
        "created_at": _utc(event.created_at),
    }


class PublicEventSummary(BaseModel):
    id: UUID
    title: str
    description: str
    type: EventType
    organizer_name: str
    participants: list[ParticipantOut]
    starts_at: datetime
    venue: VenueOut
    zones: list[ZoneSummary]
    published_at: datetime | None

    @classmethod
    def of(cls, event: Event) -> Self:
        return cls.model_validate(
            {**_common_fields(event), "zones": [ZoneSummary.of(zone) for zone in event.details.zones]}
        )


class PublicEvent(PublicEventSummary):
    zones: list[ZoneDetail]  # type: ignore[assignment]

    @classmethod
    def of(cls, event: Event) -> Self:
        return cls.model_validate(
            {**_common_fields(event), "zones": [ZoneDetail.of(zone) for zone in event.details.zones]}
        )


class ManagedEventSummary(PublicEventSummary):
    owner_id: str
    status: EventStatus
    version: int
    created_at: datetime

    @classmethod
    def of(cls, event: Event) -> Self:
        return cls.model_validate(
            {**_managed_fields(event), "zones": [ZoneSummary.of(zone) for zone in event.details.zones]}
        )


class ManagedEvent(ManagedEventSummary):
    zones: list[ZoneDetail]  # type: ignore[assignment]

    @classmethod
    def of(cls, event: Event) -> Self:
        return cls.model_validate(
            {**_managed_fields(event), "zones": [ZoneDetail.of(zone) for zone in event.details.zones]}
        )


class PublicEventPage(BaseModel):
    items: list[PublicEventSummary]
    limit: int
    offset: int
    total: int


class ManagedEventPage(BaseModel):
    items: list[ManagedEventSummary]
    limit: int
    offset: int
    total: int
