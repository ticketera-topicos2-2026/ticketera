"""Ports of the catalog application layer, implemented by the infrastructure adapters (D-33)."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, Self
from uuid import UUID

from catalog.domain.event import Event, EventType


@dataclass(frozen=True)
class Page:
    limit: int
    offset: int


@dataclass(frozen=True)
class PageResult:
    items: list[Event] = field(default_factory=list)
    total: int = 0


@dataclass(frozen=True)
class PublicFilters:
    type: EventType | None = None
    starts_from: datetime | None = None
    starts_to: datetime | None = None


@dataclass(frozen=True)
class IdempotencyRecord:
    """A reserved key: its request hash, and the event it created once the creation committed."""

    request_hash: str
    event_id: UUID | None


class EventRepository(Protocol):
    def add(self, event: Event) -> None: ...

    def get(self, event_id: UUID) -> Event | None: ...

    def get_for_update(self, event_id: UUID) -> Event | None:
        """Loads the event and locks its row until the transaction ends."""
        ...

    def update(self, event: Event, expected_version: int) -> bool:
        """Stores the event only if it is still a draft at `expected_version`; True if it did (EC-06)."""
        ...

    def list_managed(self, owner_id: str | None, page: Page) -> PageResult:
        """Events of an owner, or of every owner when `owner_id` is None, newest first."""
        ...

    def list_published(self, filters: PublicFilters, now: datetime, page: Page) -> PageResult:
        """Published events that start after `now`, earliest first."""
        ...


class IdempotencyStore(Protocol):
    def reserve(self, owner_id: str, key: UUID, request_hash: str) -> IdempotencyRecord | None:
        """Reserves the key in the current transaction (None), or returns the existing record (EC-05)."""
        ...

    def complete(self, owner_id: str, key: UUID, event_id: UUID) -> None: ...


class UnitOfWork(Protocol):
    """One transaction and the repositories that work in it."""

    @property
    def events(self) -> EventRepository: ...

    @property
    def idempotency(self) -> IdempotencyStore: ...

    def __enter__(self) -> Self: ...

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...
