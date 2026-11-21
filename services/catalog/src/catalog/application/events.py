"""Use cases of the event catalog (change e1-event-catalog; design EC-02, EC-04, EC-05, EC-06).

Spec catalog/event-management and catalog/event-browsing. Each operation runs in one unit of work; roles and
ownership are checked here, on the user value that the API layer builds from the token.
"""

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from catalog.application.access import AuthenticatedUser
from catalog.application.exceptions import EventNotFoundError, IdempotencyKeyMismatchError, NotAllowedError
from catalog.application.ports import Page, PageResult, PublicFilters, UnitOfWork
from catalog.domain.event import (
    Event,
    EventDetails,
    EventNotEditableError,
    EventStatus,
    StaleVersionError,
)


class CatalogService:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        clock: Callable[[], datetime],
        new_id: Callable[[], UUID],
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._new_id = new_id

    def create_event(
        self, user: AuthenticatedUser, details: EventDetails, idempotency_key: UUID, request_hash: str
    ) -> Event:
        """Creates a draft owned by the user, once per idempotency key (EC-05)."""
        _require_manager(user)
        with self._uow_factory() as uow:
            existing = uow.idempotency.reserve(user.sub, idempotency_key, request_hash)
            if existing is not None:
                uow.rollback()
                return self._replay(uow, existing.request_hash, existing.event_id, request_hash)
            event = Event.create(
                event_id=self._new_id(), owner_id=user.sub, details=details, now=self._clock()
            )
            uow.events.add(event)
            uow.idempotency.complete(user.sub, idempotency_key, event.id)
            uow.commit()
            return event

    def replace_event(
        self, user: AuthenticatedUser, event_id: UUID, details: EventDetails, expected_version: int
    ) -> Event:
        """Replaces a draft at its current version; refuses a stale version or a published event (EC-06)."""
        _require_manager(user)
        with self._uow_factory() as uow:
            event = _managed(uow.events.get(event_id), user)
            edited = event.replace(details, expected_version)
            if not uow.events.update(edited, expected_version):
                uow.rollback()
                _raise_conflict(_managed(uow.events.get(event_id), user))
            uow.commit()
            return edited

    def publish_event(self, user: AuthenticatedUser, event_id: UUID) -> Event:
        """Publishes a complete draft; its row stays locked until the commit, so no edit lands after it."""
        _require_manager(user)
        with self._uow_factory() as uow:
            event = _managed(uow.events.get_for_update(event_id), user)
            published, domain_event = event.publish(now=self._clock())
            if domain_event is None:
                uow.rollback()
                return published
            uow.events.update(published, expected_version=event.version)
            uow.commit()
            return published

    def get_managed_event(self, user: AuthenticatedUser, event_id: UUID) -> Event:
        _require_manager(user)
        with self._uow_factory() as uow:
            return _managed(uow.events.get(event_id), user)

    def list_managed(self, user: AuthenticatedUser, page: Page) -> PageResult:
        _require_manager(user)
        with self._uow_factory() as uow:
            return uow.events.list_managed(owner_id=None if user.is_admin else user.sub, page=page)

    def list_published(self, filters: PublicFilters, page: Page) -> PageResult:
        with self._uow_factory() as uow:
            return uow.events.list_published(filters, now=self._clock(), page=page)

    def get_published_event(self, event_id: UUID) -> Event:
        with self._uow_factory() as uow:
            event = uow.events.get(event_id)
        if event is None or event.status is not EventStatus.PUBLISHED:
            raise EventNotFoundError(str(event_id))
        return event

    @staticmethod
    def _replay(uow: UnitOfWork, stored_hash: str, event_id: UUID | None, request_hash: str) -> Event:
        if stored_hash != request_hash:
            raise IdempotencyKeyMismatchError("the idempotency key was used with a different request")
        event = uow.events.get(event_id) if event_id is not None else None
        if event is None:
            # A committed key always points to its event; anything else is a broken invariant.
            raise RuntimeError("an idempotency key was committed without its event")
        return event


def _require_manager(user: AuthenticatedUser) -> None:
    if not user.manages_events:
        raise NotAllowedError("managing events requires the EVENT_OWNER or the ADMIN role")


def _managed(event: Event | None, user: AuthenticatedUser) -> Event:
    """The event if the user may manage it; otherwise not found, the same as a missing one (EC-04)."""
    if event is None or not user.can_manage(event.owner_id):
        raise EventNotFoundError("event not found")
    return event


def _raise_conflict(current: Event) -> None:
    if current.status is not EventStatus.DRAFT:
        raise EventNotEditableError(f"event {current.id} is {current.status}")
    raise StaleVersionError(f"event {current.id} changed; it is now at version {current.version}")
