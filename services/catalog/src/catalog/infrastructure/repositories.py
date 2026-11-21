"""PostgreSQL adapters of the catalog ports (change e1-event-catalog; design EC-05, EC-06, EC-08).

Plain SQL through SQLAlchemy, as in sales (D-33). Every statement runs in the session's transaction; the
unit of work commits or rolls it back. Every value is a bound parameter; the only SQL built at run time is
the WHERE clause of a page, from conditions written in this module.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Row, text
from sqlalchemy.orm import Session

from catalog.application.ports import IdempotencyRecord, Page, PageResult, PublicFilters
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

EVENT_COLUMNS = (
    "id, owner_id, title, description, type, organizer_name, venue_name, venue_city, venue_address, "
    "starts_at, status, version, created_at, published_at"
)
INSERT_EVENT = text(
    "INSERT INTO events (id, owner_id, title, description, type, organizer_name, venue_name, venue_city, "
    "venue_address, starts_at, status, version, created_at, published_at) "
    "VALUES (:id, :owner_id, :title, :description, :type, :organizer_name, :venue_name, :venue_city, "
    ":venue_address, :starts_at, :status, :version, :created_at, :published_at)"
)
SELECT_EVENT = (
    "SELECT id, owner_id, title, description, type, organizer_name, venue_name, venue_city, venue_address, "
    "starts_at, status, version, created_at, published_at FROM events WHERE id = :id"
)


class SqlAlchemyEventRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, event: Event) -> None:
        self._session.execute(INSERT_EVENT, _event_row(event))
        self._insert_children(event)

    def get(self, event_id: UUID) -> Event | None:
        return self._load(SELECT_EVENT, event_id)

    def get_for_update(self, event_id: UUID) -> Event | None:
        return self._load(SELECT_EVENT + " FOR UPDATE", event_id)

    def update(self, event: Event, expected_version: int) -> bool:
        """Conditional update (EC-06): under READ COMMITTED a concurrent writer of the same row waits, then
        re-checks the condition against the committed row, so a stale version or a published event matches
        nothing."""
        result = self._session.execute(
            text(
                "UPDATE events SET title = :title, description = :description, type = :type, "
                "organizer_name = :organizer_name, venue_name = :venue_name, venue_city = :venue_city, "
                "venue_address = :venue_address, starts_at = :starts_at, status = :status, "
                "version = :version, published_at = :published_at "
                "WHERE id = :id AND version = :expected_version AND status = 'DRAFT'"
            ),
            {**_event_row(event), "expected_version": expected_version},
        )
        if getattr(result, "rowcount", 0) != 1:
            return False
        self._session.execute(text("DELETE FROM event_zones WHERE event_id = :id"), {"id": event.id})
        self._session.execute(text("DELETE FROM event_participants WHERE event_id = :id"), {"id": event.id})
        self._insert_children(event)
        return True

    def list_managed(self, owner_id: str | None, page: Page) -> PageResult:
        condition = "owner_id = :owner_id" if owner_id is not None else "TRUE"
        return self._page(condition, {"owner_id": owner_id}, "created_at DESC, id", page)

    def list_published(self, filters: PublicFilters, now: datetime, page: Page) -> PageResult:
        conditions = ["status = 'PUBLISHED'", "starts_at > :now"]
        params: dict[str, Any] = {"now": now}
        if filters.type is not None:
            conditions.append("type = :type")
            params["type"] = filters.type.value
        if filters.starts_from is not None:
            conditions.append("starts_at >= :starts_from")
            params["starts_from"] = filters.starts_from
        if filters.starts_to is not None:
            conditions.append("starts_at <= :starts_to")
            params["starts_to"] = filters.starts_to
        return self._page(" AND ".join(conditions), params, "starts_at, id", page)

    def _page(self, condition: str, params: dict[str, Any], order: str, page: Page) -> PageResult:
        # The condition and the order come from this module only; every value is a bound parameter.
        count_query = text(f"SELECT count(*) FROM events WHERE {condition}")  # noqa: S608
        total = self._session.execute(count_query, params).scalar_one()
        rows = self._session.execute(
            text(
                f"SELECT {EVENT_COLUMNS} FROM events WHERE {condition} ORDER BY {order} "  # noqa: S608
                "LIMIT :limit OFFSET :offset"
            ),
            {**params, "limit": page.limit, "offset": page.offset},
        ).all()
        return PageResult(items=self._with_children(rows), total=total)

    def _load(self, query: str, event_id: UUID) -> Event | None:
        row = self._session.execute(text(query), {"id": event_id}).one_or_none()
        return self._with_children([row])[0] if row is not None else None

    def _with_children(self, rows: Sequence[Row[Any]]) -> list[Event]:
        if not rows:
            return []
        ids = [row.id for row in rows]
        zones: dict[UUID, list[Zone]] = {event_id: [] for event_id in ids}
        participants: dict[UUID, list[Participant]] = {event_id: [] for event_id in ids}
        for zone in self._session.execute(
            text(
                "SELECT event_id, code, name, modality, seat_count, capacity FROM event_zones "
                "WHERE event_id = ANY(:ids) ORDER BY event_id, position"
            ),
            {"ids": ids},
        ):
            zones[zone.event_id].append(
                Zone(
                    code=zone.code,
                    name=zone.name,
                    modality=TicketModality(zone.modality),
                    seat_count=zone.seat_count,
                    capacity=zone.capacity,
                )
            )
        for participant in self._session.execute(
            text(
                "SELECT event_id, name FROM event_participants WHERE event_id = ANY(:ids) "
                "ORDER BY event_id, position"
            ),
            {"ids": ids},
        ):
            participants[participant.event_id].append(Participant(participant.name))
        return [_event(row, tuple(zones[row.id]), tuple(participants[row.id])) for row in rows]

    def _insert_children(self, event: Event) -> None:
        for position, zone in enumerate(event.details.zones):
            self._session.execute(
                text(
                    "INSERT INTO event_zones (event_id, position, code, name, modality, seat_count, "
                    "capacity) VALUES (:event_id, :position, :code, :name, :modality, :seat_count, :capacity)"
                ),
                {
                    "event_id": event.id,
                    "position": position,
                    "code": zone.code,
                    "name": zone.name,
                    "modality": zone.modality.value,
                    "seat_count": zone.seat_count,
                    "capacity": zone.capacity,
                },
            )
        for position, participant in enumerate(event.details.participants):
            self._session.execute(
                text(
                    "INSERT INTO event_participants (event_id, position, name) "
                    "VALUES (:event_id, :position, :name)"
                ),
                {"event_id": event.id, "position": position, "name": participant.name},
            )


class SqlAlchemyIdempotencyStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def reserve(self, owner_id: str, key: UUID, request_hash: str) -> IdempotencyRecord | None:
        """Inserts the key first (EC-05). If another transaction holds the same key, PostgreSQL waits for
        it to end; then the insert either succeeds (it rolled back) or finds the committed record."""
        inserted = self._session.execute(
            text(
                "INSERT INTO idempotency_keys (owner_id, key, request_hash) VALUES (:owner_id, :key, :hash) "
                "ON CONFLICT (owner_id, key) DO NOTHING RETURNING key"
            ),
            {"owner_id": owner_id, "key": key, "hash": request_hash},
        ).one_or_none()
        if inserted is not None:
            return None
        row = self._session.execute(
            text(
                "SELECT request_hash, event_id FROM idempotency_keys "
                "WHERE owner_id = :owner_id AND key = :key"
            ),
            {"owner_id": owner_id, "key": key},
        ).one()
        return IdempotencyRecord(request_hash=row.request_hash, event_id=row.event_id)

    def complete(self, owner_id: str, key: UUID, event_id: UUID) -> None:
        self._session.execute(
            text(
                "UPDATE idempotency_keys SET event_id = :event_id WHERE owner_id = :owner_id AND key = :key"
            ),
            {"owner_id": owner_id, "key": key, "event_id": event_id},
        )


def _event_row(event: Event) -> dict[str, Any]:
    details = event.details
    return {
        "id": event.id,
        "owner_id": event.owner_id,
        "title": details.title,
        "description": details.description,
        "type": details.type.value,
        "organizer_name": details.organizer_name,
        "venue_name": details.venue.name,
        "venue_city": details.venue.city,
        "venue_address": details.venue.address,
        "starts_at": details.starts_at,
        "status": event.status.value,
        "version": event.version,
        "created_at": event.created_at,
        "published_at": event.published_at,
    }


def _utc(moment: datetime | None) -> datetime | None:
    return moment.astimezone(UTC) if moment is not None else None


def _event(row: Row[Any], zones: tuple[Zone, ...], participants: tuple[Participant, ...]) -> Event:
    starts_at = _utc(row.starts_at)
    created_at = _utc(row.created_at)
    assert starts_at is not None and created_at is not None  # noqa: S101 - NOT NULL columns
    return Event(
        id=row.id,
        owner_id=row.owner_id,
        details=EventDetails(
            title=row.title,
            description=row.description,
            type=EventType(row.type),
            organizer_name=row.organizer_name,
            participants=participants,
            starts_at=starts_at,
            venue=Venue(name=row.venue_name, city=row.venue_city, address=row.venue_address),
            zones=zones,
        ),
        status=EventStatus(row.status),
        version=row.version,
        created_at=created_at,
        published_at=_utc(row.published_at),
    )
