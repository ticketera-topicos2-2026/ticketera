"""In-memory fakes of the catalog ports, for the application tests (change e1-event-catalog, task 2.1)."""

from datetime import datetime
from typing import Self
from uuid import UUID

from catalog.application.ports import IdempotencyRecord, Page, PageResult, PublicFilters
from catalog.domain.event import Event, EventStatus


class FakeEventRepository:
    def __init__(self) -> None:
        self.events: dict[UUID, Event] = {}

    def add(self, event: Event) -> None:
        self.events[event.id] = event

    def get(self, event_id: UUID) -> Event | None:
        return self.events.get(event_id)

    def get_for_update(self, event_id: UUID) -> Event | None:
        return self.events.get(event_id)

    def update(self, event: Event, expected_version: int) -> bool:
        current = self.events.get(event.id)
        if current is None or current.version != expected_version or current.status is not EventStatus.DRAFT:
            return False
        self.events[event.id] = event
        return True

    def list_managed(self, owner_id: str | None, page: Page) -> PageResult:
        items = [event for event in self.events.values() if owner_id is None or event.owner_id == owner_id]
        items.sort(key=lambda event: event.created_at, reverse=True)
        return PageResult(items=items[page.offset : page.offset + page.limit], total=len(items))

    def list_published(self, filters: PublicFilters, now: datetime, page: Page) -> PageResult:
        items = [
            event
            for event in self.events.values()
            if event.status is EventStatus.PUBLISHED
            and event.details.starts_at > now
            and (filters.type is None or event.details.type is filters.type)
            and (filters.starts_from is None or event.details.starts_at >= filters.starts_from)
            and (filters.starts_to is None or event.details.starts_at <= filters.starts_to)
        ]
        items.sort(key=lambda event: event.details.starts_at)
        return PageResult(items=items[page.offset : page.offset + page.limit], total=len(items))


class FakeIdempotencyStore:
    def __init__(self) -> None:
        self.records: dict[tuple[str, UUID], IdempotencyRecord] = {}

    def reserve(self, owner_id: str, key: UUID, request_hash: str) -> IdempotencyRecord | None:
        existing = self.records.get((owner_id, key))
        if existing is not None:
            return existing
        self.records[(owner_id, key)] = IdempotencyRecord(request_hash=request_hash, event_id=None)
        return None

    def complete(self, owner_id: str, key: UUID, event_id: UUID) -> None:
        record = self.records[(owner_id, key)]
        self.records[(owner_id, key)] = IdempotencyRecord(request_hash=record.request_hash, event_id=event_id)


class FakeUnitOfWork:
    """Keeps every change at once; commits and rollbacks are only counted."""

    def __init__(self) -> None:
        self.events = FakeEventRepository()
        self.idempotency = FakeIdempotencyStore()
        self.commits = 0
        self.rollbacks = 0

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        if exc_type is not None:
            self.rollback()

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1
