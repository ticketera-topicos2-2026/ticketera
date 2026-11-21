"""Acceptance tests of the catalog management API (change e1-event-catalog, task 4.4; spec
catalog/event-management; design EC-04, EC-05, EC-06, EC-10)."""

from datetime import timedelta
from uuid import uuid4

import pytest

from tests.acceptance.support import (
    ADMIN,
    ADMIN_SUB,
    CLIENT,
    NOW,
    OTHER_OWNER,
    OWNER,
    OWNER_SUB,
    client,
    create,
    error_fields,
    event_body,
    publish,
    with_key,
)


def test_event_owner_creates_a_draft() -> None:
    """Req: An EVENT_OWNER or an ADMIN creates a draft event. Scenario: EVENT_OWNER creates a draft."""
    response = client().post("/manage/events", json=event_body(), headers=with_key(OWNER))

    body = response.json()
    assert response.status_code == 201
    assert (body["status"], body["version"], body["owner_id"]) == ("DRAFT", 1, OWNER_SUB)
    assert len(body["id"]) == 36


def test_admin_creates_a_draft() -> None:
    """Req: An EVENT_OWNER or an ADMIN creates a draft event. Scenario: ADMIN creates a draft."""
    assert create(client(), ADMIN)["owner_id"] == ADMIN_SUB


def test_client_cannot_create_an_event() -> None:
    """Req: An EVENT_OWNER or an ADMIN creates a draft event. Scenario: CLIENT tries to create an event."""
    test_client = client()

    response = test_client.post("/manage/events", json=event_body(), headers=with_key(CLIENT))

    assert response.status_code == 403
    assert test_client.get("/manage/events", headers=ADMIN).json()["total"] == 0


def test_missing_title_and_unknown_type_are_named() -> None:
    """Req: Event data is validated. Scenario: Missing title and unknown type."""
    body = event_body(type="PARTY")
    del body["title"]

    response = client().post("/manage/events", json=body, headers=with_key(OWNER))

    assert response.status_code == 422
    assert {"title", "type"} <= error_fields(response.json())


def test_empty_title_is_named() -> None:
    """Req: Event data is validated (rules checked by the domain are named the same way)."""
    response = client().post("/manage/events", json=event_body(title="  "), headers=with_key(OWNER))

    assert response.status_code == 422
    assert error_fields(response.json()) == {"title"}


def test_start_without_time_zone_is_named() -> None:
    """Req: Event data is validated. Scenario: Start time without a time zone."""
    response = client().post(
        "/manage/events", json=event_body(starts_at="2026-12-20T21:00:00"), headers=with_key(OWNER)
    )

    assert response.status_code == 422
    assert error_fields(response.json()) == {"starts_at"}


def test_too_many_participants_are_named() -> None:
    """Req: Event data is validated. Scenario: Too many participants."""
    participants = [{"name": f"Participante {n}"} for n in range(51)]

    response = client().post(
        "/manage/events", json=event_body(participants=participants), headers=with_key(OWNER)
    )

    assert response.status_code == 422
    assert error_fields(response.json()) == {"participants"}


@pytest.mark.parametrize("field", ["owner_id", "status", "version", "published_at"])
def test_fields_outside_the_contract_are_rejected(field: str) -> None:
    """Req: Fields outside the contract are rejected. Scenario: Client tries to set the owner or the state."""
    test_client = client()

    response = test_client.post("/manage/events", json={**event_body(), field: "x"}, headers=with_key(OWNER))

    assert response.status_code == 422
    assert field in error_fields(response.json())
    assert test_client.get("/manage/events", headers=ADMIN).json()["total"] == 0


def test_numbered_zone_shows_its_seat_ids() -> None:
    """Req: Each zone has a ticket modality. Scenarios: Numbered zone; Unnumbered zone."""
    zones = {zone["code"]: zone for zone in create(client())["zones"]}

    assert zones["PLATEA"]["seat_ids"] == ["PLATEA-1", "PLATEA-2", "PLATEA-3"]
    assert (zones["CAMPO"]["capacity"], zones["CAMPO"]["seat_ids"]) == (8000, [])


def test_numbered_zone_with_a_capacity_is_named() -> None:
    """Req: Each zone has a ticket modality. Scenario: Numbered zone with a capacity."""
    zones = [{"code": "A", "name": "A", "modality": "NUMBERED", "capacity": 100}]

    response = client().post("/manage/events", json=event_body(zones=zones), headers=with_key(OWNER))

    assert response.status_code == 422
    assert error_fields(response.json()) == {"zones.0"}


def test_repeated_zone_code_is_named() -> None:
    """Req: Each zone has a ticket modality. Scenario: Repeated zone code."""
    zone = {"code": "A", "name": "A", "modality": "UNNUMBERED", "capacity": 10}

    response = client().post("/manage/events", json=event_body(zones=[zone, zone]), headers=with_key(OWNER))

    assert response.status_code == 422
    assert error_fields(response.json()) == {"zones"}


@pytest.mark.parametrize("key", [None, "not-a-uuid"])
def test_missing_or_malformed_key_is_a_bad_request(key: str | None) -> None:
    """Req: Event creation is idempotent. Scenario: Missing key."""
    headers = OWNER if key is None else {**OWNER, "Idempotency-Key": key}
    test_client = client()

    response = test_client.post("/manage/events", json=event_body(), headers=headers)

    assert response.status_code == 400
    assert test_client.get("/manage/events", headers=OWNER).json()["total"] == 0


def test_retry_with_the_same_key_returns_the_same_event() -> None:
    """Req: Event creation is idempotent. Scenario: Retry after a network timeout."""
    test_client = client()
    headers = with_key(OWNER)

    first = test_client.post("/manage/events", json=event_body(), headers=headers)
    second = test_client.post("/manage/events", json=event_body(), headers=headers)

    assert (first.status_code, second.status_code) == (201, 201)
    assert second.json()["id"] == first.json()["id"]
    assert test_client.get("/manage/events", headers=OWNER).json()["total"] == 1


def test_same_key_with_a_different_body_is_rejected() -> None:
    """Req: Event creation is idempotent. Scenario: Same key with a different body."""
    test_client = client()
    headers = with_key(OWNER)
    test_client.post("/manage/events", json=event_body(), headers=headers)

    response = test_client.post("/manage/events", json=event_body(title="Otro"), headers=headers)

    assert response.status_code == 422
    assert test_client.get("/manage/events", headers=OWNER).json()["total"] == 1


def test_two_users_with_the_same_key_create_two_events() -> None:
    """Req: Event creation is idempotent. Scenario: Two users with the same key."""
    test_client = client()
    key = str(uuid4())

    for headers in (OWNER, ADMIN):
        assert (
            test_client.post(
                "/manage/events", json=event_body(), headers={**headers, "Idempotency-Key": key}
            ).status_code
            == 201
        )

    assert test_client.get("/manage/events", headers=ADMIN).json()["total"] == 2


def test_edit_with_the_current_version() -> None:
    """Req: A draft is edited with its current version. Scenario: Edit with the current version."""
    test_client = client()
    event_id = create(test_client)["id"]

    response = test_client.put(
        f"/manage/events/{event_id}", json=event_body(title="Nuevo", version=1), headers=OWNER
    )

    assert response.status_code == 200
    assert (response.json()["title"], response.json()["version"]) == ("Nuevo", 2)


def test_edit_with_a_stale_version() -> None:
    """Req: A draft is edited with its current version. Scenario: Edit with a stale version."""
    test_client = client()
    event_id = create(test_client)["id"]
    test_client.put(f"/manage/events/{event_id}", json=event_body(title="v2", version=1), headers=OWNER)

    response = test_client.put(
        f"/manage/events/{event_id}", json=event_body(title="v3", version=1), headers=ADMIN
    )

    assert response.status_code == 409
    assert test_client.get(f"/manage/events/{event_id}", headers=OWNER).json()["title"] == "v2"


def test_edit_of_a_published_event() -> None:
    """Req: A draft is edited with its current version. Scenario: Edit of a published event."""
    test_client = client()
    event_id = create(test_client)["id"]
    version = publish(test_client, event_id)["version"]

    response = test_client.put(
        f"/manage/events/{event_id}", json=event_body(title="Otro", version=version), headers=OWNER
    )

    assert response.status_code == 409


def test_complete_draft_is_published_and_listed() -> None:
    """Req: A draft is published once it is complete. Scenario: Complete draft published."""
    test_client = client()
    event_id = create(test_client)["id"]

    published = publish(test_client, event_id)

    assert (published["status"], published["published_at"]) == (
        "PUBLISHED",
        NOW.isoformat().replace("+00:00", "Z"),
    )
    assert [item["id"] for item in test_client.get("/events").json()["items"]] == [event_id]


def test_draft_without_zones_is_not_published() -> None:
    """Req: A draft is published once it is complete. Scenario: Draft without zones."""
    test_client = client()
    event_id = create(test_client, zones=[])["id"]

    response = test_client.post(f"/manage/events/{event_id}/publish", headers=OWNER)

    assert response.status_code == 422
    assert error_fields(response.json()) == {"zones"}
    assert test_client.get(f"/manage/events/{event_id}", headers=OWNER).json()["status"] == "DRAFT"


def test_draft_that_starts_in_the_past_is_not_published() -> None:
    """Req: A draft is published once it is complete. Scenario: Draft that starts in the past."""
    test_client = client()
    event_id = create(test_client, starts_at=(NOW - timedelta(hours=1)).isoformat())["id"]

    response = test_client.post(f"/manage/events/{event_id}/publish", headers=OWNER)

    assert response.status_code == 422
    assert error_fields(response.json()) == {"starts_at"}


def test_publishing_twice_keeps_the_first_publication() -> None:
    """Req: A draft is published once it is complete. Scenario: Publishing twice."""
    test_client = client()
    event_id = create(test_client)["id"]
    first = publish(test_client, event_id)

    second = publish(test_client, event_id)

    assert second == first


def test_another_owners_draft_is_not_found() -> None:
    """Req: An EVENT_OWNER manages only their own events.

    Scenario: EVENT_OWNER reads another owner's draft.
    """
    test_client = client()
    event_id = create(test_client, ADMIN)["id"]

    response = test_client.get(f"/manage/events/{event_id}", headers=OWNER)
    unknown = test_client.get(f"/manage/events/{uuid4()}", headers=OWNER)

    assert (response.status_code, unknown.status_code) == (404, 404)
    assert response.json() == unknown.json()


def test_another_owners_draft_is_not_published() -> None:
    """Req: An EVENT_OWNER manages only their own events.

    Scenario: EVENT_OWNER publishes another owner's draft.
    """
    test_client = client()
    event_id = create(test_client, OTHER_OWNER)["id"]

    assert test_client.post(f"/manage/events/{event_id}/publish", headers=OWNER).status_code == 404
    assert test_client.get(f"/manage/events/{event_id}", headers=OTHER_OWNER).json()["status"] == "DRAFT"


def test_admin_edits_an_owners_draft() -> None:
    """Req: An EVENT_OWNER manages only their own events. Scenario: ADMIN edits an EVENT_OWNER's draft."""
    test_client = client()
    event_id = create(test_client)["id"]

    response = test_client.put(
        f"/manage/events/{event_id}", json=event_body(title="Corregido", version=1), headers=ADMIN
    )

    assert response.status_code == 200
    assert response.json()["owner_id"] == OWNER_SUB


def test_event_owner_lists_their_events_and_admin_lists_all() -> None:
    """Req: Managers list the events they can manage. Scenarios: EVENT_OWNER lists their events; ADMIN lists
    every event."""
    test_client = client()
    draft_id = create(test_client)["id"]
    published_id = create(test_client, title="Publicado")["id"]
    publish(test_client, published_id)
    create(test_client, OTHER_OWNER)

    mine = test_client.get("/manage/events", headers=OWNER).json()
    everything = test_client.get("/manage/events", headers=ADMIN).json()

    assert {item["id"] for item in mine["items"]} == {draft_id, published_id}
    assert everything["total"] == 3


def test_limit_above_the_maximum_is_rejected() -> None:
    """Req: Managers list the events they can manage. Scenario: Limit above the maximum."""
    response = client().get("/manage/events", params={"limit": 500}, headers=ADMIN)

    assert response.status_code == 422
    assert error_fields(response.json()) == {"limit"}
