"""Routers of the catalog API (change e1-event-catalog; design EC-02, EC-04, EC-05, EC-11).

Two APIs (EC-02): the public catalog under /events, which takes no token and ignores any token it
receives, and the management API under /manage/events, for EVENT_OWNER and ADMIN users.
"""

import hashlib
import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import AwareDatetime

from catalog.api.auth import event_manager
from catalog.api.schemas import (
    EventInput,
    EventReplacement,
    ManagedEvent,
    ManagedEventPage,
    ManagedEventSummary,
    PublicEvent,
    PublicEventPage,
    PublicEventSummary,
)
from catalog.application.access import AuthenticatedUser
from catalog.application.events import CatalogService
from catalog.application.exceptions import EventNotFoundError
from catalog.application.ports import Page, PublicFilters
from catalog.domain.event import EventType

MAX_PAGE_SIZE = 100

public_router = APIRouter()
manage_router = APIRouter(prefix="/manage")


def catalog_service(request: Request) -> CatalogService:
    service: CatalogService = request.app.state.catalog_service
    return service


Catalog = Annotated[CatalogService, Depends(catalog_service)]
Manager = Annotated[AuthenticatedUser, Depends(event_manager)]
Limit = Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)]
Offset = Annotated[int, Query(ge=0)]


@public_router.get("/events", operation_id="list_published_events", response_model=PublicEventPage)
@public_router.head("/events", operation_id="head_published_events", response_model=PublicEventPage)
def list_published_events(
    catalog: Catalog,
    type: EventType | None = None,
    starts_from: AwareDatetime | None = None,
    starts_to: AwareDatetime | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
) -> PublicEventPage:
    filters = PublicFilters(type=type, starts_from=starts_from, starts_to=starts_to)
    result = catalog.list_published(filters, Page(limit=limit, offset=offset))
    items = [PublicEventSummary.of(event) for event in result.items]
    return PublicEventPage(items=items, limit=limit, offset=offset, total=result.total)


@public_router.get("/events/{event_id}", operation_id="get_published_event", response_model=PublicEvent)
@public_router.head("/events/{event_id}", operation_id="head_published_event", response_model=PublicEvent)
def get_published_event(event_id: str, catalog: Catalog) -> PublicEvent:
    return PublicEvent.of(catalog.get_published_event(_event_id(event_id)))


@manage_router.post(
    "/events", operation_id="create_event", status_code=status.HTTP_201_CREATED, response_model=ManagedEvent
)
def create_event(
    user: Manager,
    body: EventInput,
    catalog: Catalog,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ManagedEvent:
    key = _idempotency_key(idempotency_key)
    event = catalog.create_event(
        user, body.to_details(), idempotency_key=key, request_hash=_request_hash(body)
    )
    return ManagedEvent.of(event)


@manage_router.get("/events", operation_id="list_managed_events", response_model=ManagedEventPage)
def list_managed_events(
    user: Manager, catalog: Catalog, limit: Limit = 20, offset: Offset = 0
) -> ManagedEventPage:
    result = catalog.list_managed(user, Page(limit=limit, offset=offset))
    items = [ManagedEventSummary.of(event) for event in result.items]
    return ManagedEventPage(items=items, limit=limit, offset=offset, total=result.total)


@manage_router.get("/events/{event_id}", operation_id="get_managed_event", response_model=ManagedEvent)
def get_managed_event(event_id: str, user: Manager, catalog: Catalog) -> ManagedEvent:
    return ManagedEvent.of(catalog.get_managed_event(user, _event_id(event_id)))


@manage_router.put("/events/{event_id}", operation_id="replace_event", response_model=ManagedEvent)
def replace_event(event_id: str, user: Manager, body: EventReplacement, catalog: Catalog) -> ManagedEvent:
    event = catalog.replace_event(user, _event_id(event_id), body.to_details(), expected_version=body.version)
    return ManagedEvent.of(event)


@manage_router.post("/events/{event_id}/publish", operation_id="publish_event", response_model=ManagedEvent)
def publish_event(event_id: str, user: Manager, catalog: Catalog) -> ManagedEvent:
    return ManagedEvent.of(catalog.publish_event(user, _event_id(event_id)))


def _event_id(raw: str) -> UUID:
    """A path id that is not a UUID is an event that does not exist: the same 404 as any other (EC-04)."""
    try:
        return UUID(raw)
    except ValueError as error:
        raise EventNotFoundError(raw) from error


def _idempotency_key(raw: str | None) -> UUID:
    """A missing or malformed key answers 400, not FastAPI's default 422 (spec: Missing key)."""
    if raw is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="The Idempotency-Key header is required"
        )
    try:
        return UUID(raw)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="The Idempotency-Key header must be a UUID"
        ) from error


def _request_hash(body: EventInput) -> str:
    """SHA-256 of the canonical JSON of the body: the same event sent twice gives the same hash (EC-05)."""
    canonical = json.dumps(body.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()
