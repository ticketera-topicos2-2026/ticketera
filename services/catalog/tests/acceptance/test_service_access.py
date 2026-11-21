"""Acceptance tests of the token-claims contract on the catalog management API (change e1-event-catalog,
task 4.2; spec catalog/service-access)."""

import base64
import json

from tests.acceptance.support import (
    ADMIN,
    CLIENT_SUB,
    OTHER_OWNER,
    OWNER,
    OWNER_SUB,
    bearer,
    client,
    create,
    event_body,
    token,
    with_key,
)

DEFAULT_ROLES = ("offline_access", "uma_authorization", "default-roles-ticketera")


def test_only_platform_roles_count() -> None:
    """Req: Services take roles only from the platform roles in realm_access.roles.

    Scenario: Default roles of the identity service.
    """
    test_client = client()

    as_client = test_client.get("/manage/events", headers=bearer(CLIENT_SUB, "CLIENT", *DEFAULT_ROLES))
    as_owner = test_client.get("/manage/events", headers=bearer(OWNER_SUB, "EVENT_OWNER", *DEFAULT_ROLES))

    assert as_client.status_code == 403
    assert as_owner.status_code == 200


def test_role_in_another_claim_is_ignored() -> None:
    """Req: Services take roles only from the platform roles in realm_access.roles.

    Scenario: Role in another claim.
    """
    headers = bearer(
        CLIENT_SUB,
        "CLIENT",
        extra_claims={"resource_access": {"catalog": {"roles": ["ADMIN"]}}, "role": "ADMIN"},
    )

    assert client().get("/manage/events", headers=headers).status_code == 403


def test_token_without_realm_roles_holds_no_role() -> None:
    """Req: Services take roles only from the platform roles in realm_access.roles.

    Scenario: Token without realm roles.
    """
    payload = {"sub": OWNER_SUB}
    segment = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    headers = {"Authorization": f"Bearer eyJhbGciOiJSUzI1NiJ9.{segment}.c2ln"}

    assert client().get("/manage/events", headers=headers).status_code == 403


def test_forged_identity_header_is_ignored() -> None:
    """Req: Services identify the user only from the token. Scenario: Forged identity header."""
    test_client = client()
    create(test_client, OWNER)

    response = test_client.get("/manage/events", headers={**OTHER_OWNER, "X-User-Id": OWNER_SUB})

    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_forged_role_in_the_body_is_ignored() -> None:
    """Req: Services identify the user only from the token. Scenario: Forged role in the body."""
    test_client = client()
    body = {**event_body(), "roles": ["ADMIN"]}

    response = test_client.post("/manage/events", json=body, headers=with_key(bearer(CLIENT_SUB, "CLIENT")))

    assert response.status_code == 403
    assert test_client.get("/manage/events", headers=ADMIN).json()["total"] == 0


def test_client_cannot_manage_events() -> None:
    """Req: Services authorize by role. Scenarios: CLIENT calls an ADMIN-only endpoint; EVENT_OWNER calls an
    ADMIN-only endpoint (the management API admits EVENT_OWNER and ADMIN only)."""
    test_client = client()

    response = test_client.post(
        "/manage/events", json=event_body(), headers=with_key(bearer(CLIENT_SUB, "CLIENT"))
    )

    assert response.status_code == 403
    assert test_client.get("/manage/events", headers=ADMIN).json()["total"] == 0


def test_admin_is_allowed() -> None:
    """Req: Services authorize by role. Scenario: ADMIN calls an ADMIN-only endpoint."""
    assert client().get("/manage/events", headers=ADMIN).status_code == 200


def test_missing_token_is_unauthorized() -> None:
    """Req: Services authorize by role. Scenario: Protected endpoint reached without a token."""
    response = client().get("/manage/events")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_token_is_decoded_without_calling_the_identity_service() -> None:
    """Req: Services trust the token validated by the gateway. Scenario: Valid token forwarded by the gateway.

    The test app has no identity service to call: an accepted token proves the payload alone was read.
    """
    created = create(client(), OWNER)

    assert created["owner_id"] == OWNER_SUB


def test_undecodable_payload_is_unauthorized() -> None:
    """Req: Services trust the token validated by the gateway. Scenario: Payload that cannot be decoded."""
    not_json = base64.urlsafe_b64encode(b"not json").rstrip(b"=").decode()

    for value in (f"Bearer eyJhbGciOiJSUzI1NiJ9.{not_json}.c2ln", "Bearer x", "Basic dXNlcjpwYXNz"):
        response = client().get("/manage/events", headers={"Authorization": value})
        assert response.status_code == 401, value


def test_token_in_the_query_string_is_not_accepted() -> None:
    """Req: Services never expose or accept tokens outside the Authorization header.

    Scenario: Token in the query string.
    """
    response = client().get("/manage/events", params={"access_token": token(OWNER_SUB, "EVENT_OWNER")})

    assert response.status_code == 401
