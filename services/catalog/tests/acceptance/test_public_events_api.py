"""Acceptance tests of the public catalog API (change e1-event-catalog, task 4.4; spec catalog/event-browsing;
design EC-02, EC-11)."""

import base64
import json
from datetime import timedelta
from uuid import uuid4

from tests.acceptance.support import (
    ADMIN_SUB,
    NOW,
    OWNER,
    OWNER_SUB,
    bearer,
    client,
    create,
    error_fields,
    publish,
)


def published(test_client: object, **changes: object) -> str:
    event_id: str = create(test_client, **changes)["id"]  # type: ignore[arg-type]
    publish(test_client, event_id)  # type: ignore[arg-type]
    return event_id


def test_visitor_lists_published_upcoming_events_earliest_first() -> None:
    """Req: The public catalog lists only published events. Scenario: Visitor without a token."""
    test_client = client()
    later = published(test_client, title="Después", starts_at=(NOW + timedelta(days=40)).isoformat())
    sooner = published(test_client, title="Antes", starts_at=(NOW + timedelta(days=10)).isoformat())

    response = test_client.get("/events")

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [sooner, later]


def test_draft_is_not_listed() -> None:
    """Req: The public catalog lists only published events. Scenario: Draft not listed."""
    test_client = client()
    create(test_client, title="Borrador")

    assert test_client.get("/events").json()["items"] == []


def test_owner_is_not_shown() -> None:
    """Req: The public catalog lists only published events. Scenario: Owner not shown."""
    test_client = client()
    event_id = published(test_client)

    listed = test_client.get("/events").text
    detail = test_client.get(f"/events/{event_id}").text

    assert OWNER_SUB not in listed
    assert OWNER_SUB not in detail
    assert "owner_id" not in listed


def test_filter_by_type_and_date_range() -> None:
    """Req: The public catalog is filtered and paginated. Scenario: Filter by type and date range."""
    test_client = client()
    december = published(test_client, starts_at="2026-12-15T21:00:00-03:00")
    published(test_client, starts_at="2027-01-15T21:00:00-03:00")
    published(test_client, type="THEATER", starts_at="2026-12-16T21:00:00-03:00")

    response = test_client.get(
        "/events",
        params={"type": "CONCERT", "starts_from": "2026-12-01T00:00:00-03:00", "starts_to": "2026-12-31T23:59:59-03:00"},
    )

    assert [item["id"] for item in response.json()["items"]] == [december]


def test_second_page() -> None:
    """Req: The public catalog is filtered and paginated. Scenario: Second page."""
    test_client = client()
    ids = [published(test_client, starts_at=(NOW + timedelta(days=day)).isoformat()) for day in range(1, 26)]

    page = test_client.get("/events", params={"limit": 10, "offset": 20}).json()

    assert [item["id"] for item in page["items"]] == ids[20:]
    assert (page["total"], page["limit"], page["offset"]) == (25, 10, 20)


def test_invalid_type_is_rejected() -> None:
    """Req: The public catalog is filtered and paginated. Scenario: Invalid type."""
    response = client().get("/events", params={"type": "PARTY"})

    assert response.status_code == 422
    assert error_fields(response.json()) == {"type"}


def test_published_event_shows_seat_ids_and_the_list_does_not() -> None:
    """Req: The public catalog shows a published event. Scenario: Published event."""
    test_client = client()
    event_id = published(test_client)

    detail = test_client.get(f"/events/{event_id}").json()
    summary = test_client.get("/events").json()["items"][0]

    platea = next(zone for zone in detail["zones"] if zone["code"] == "PLATEA")
    assert platea["seat_ids"] == ["PLATEA-1", "PLATEA-2", "PLATEA-3"]
    assert all("seat_ids" not in zone for zone in summary["zones"])


def test_draft_and_unknown_ids_answer_the_same_404() -> None:
    """Req: The public catalog shows a published event. Scenario: Draft requested by its identifier."""
    test_client = client()
    draft_id = create(test_client)["id"]

    draft = test_client.get(f"/events/{draft_id}")
    unknown = test_client.get(f"/events/{uuid4()}")
    malformed = test_client.get("/events/not-a-uuid")

    assert (draft.status_code, unknown.status_code, malformed.status_code) == (404, 404, 404)
    assert draft.json() == unknown.json() == malformed.json()


def test_owners_token_does_not_reveal_a_draft() -> None:
    """Req: The public catalog ignores tokens. Scenario: Owner's token on the public endpoint."""
    test_client = client()
    draft_id = create(test_client)["id"]

    assert test_client.get(f"/events/{draft_id}", headers=OWNER).status_code == 404


def test_tampered_token_changes_nothing() -> None:
    """Req: The public catalog ignores tokens. Scenario: Tampered token on a public path."""
    test_client = client()
    published(test_client)
    create(test_client, title="Borrador")
    forged_payload = base64.urlsafe_b64encode(json.dumps({"sub": ADMIN_SUB, "realm_access": {"roles": ["ADMIN"]}}).encode())
    tampered = {"Authorization": f"Bearer eyJhbGciOiJSUzI1NiJ9.{forged_payload.decode().rstrip('=')}.forged"}

    anonymous = test_client.get("/events").json()

    assert test_client.get("/events", headers=tampered).json() == anonymous
    assert test_client.get("/events", headers={"Authorization": "Bearer x"}).json() == anonymous


def test_write_method_on_the_public_path_is_not_allowed() -> None:
    """Req: The public catalog ignores tokens. Scenario: Write method on the public path."""
    test_client = client()

    response = test_client.post("/events", json={}, headers=bearer(OWNER_SUB, "EVENT_OWNER"))

    assert response.status_code == 405
    assert test_client.get("/events").json()["total"] == 0


def test_head_is_answered_on_public_paths() -> None:
    """Req: The public catalog ignores tokens (it accepts GET and HEAD)."""
    test_client = client()
    event_id = published(test_client)

    assert test_client.head("/events").status_code == 200
    assert test_client.head(f"/events/{event_id}").status_code == 200
