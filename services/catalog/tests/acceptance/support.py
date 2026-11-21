"""Helpers of the catalog acceptance tests: the real app in process, with in-memory adapters and test tokens.

Tokens are unsigned JWTs, as the service trusts the gateway's validation and only decodes the payload
(token-claims contract of e1-identity-access).
"""

import base64
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient

from catalog.api.app import create_app
from tests.unit.fakes import FakeUnitOfWork

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)
OWNER_SUB = "a1f0c2d3-0000-4000-8000-000000000001"
OTHER_OWNER_SUB = "a1f0c2d3-0000-4000-8000-000000000002"
ADMIN_SUB = "a1f0c2d3-0000-4000-8000-000000000003"
CLIENT_SUB = "a1f0c2d3-0000-4000-8000-000000000004"


class ReachableProbe:
    def is_reachable(self) -> bool:
        return True


def _segment(value: dict[str, Any]) -> str:
    return base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b"=").decode()


def token(sub: str, *roles: str, extra_claims: dict[str, Any] | None = None) -> str:
    payload: dict[str, Any] = {"sub": sub, "realm_access": {"roles": list(roles)}, **(extra_claims or {})}
    return f"{_segment({'alg': 'RS256', 'typ': 'JWT'})}.{_segment(payload)}.c2lnbmF0dXJl"


def bearer(sub: str, *roles: str, extra_claims: dict[str, Any] | None = None) -> dict[str, str]:
    return {"Authorization": f"Bearer {token(sub, *roles, extra_claims=extra_claims)}"}


OWNER = bearer(OWNER_SUB, "EVENT_OWNER")
OTHER_OWNER = bearer(OTHER_OWNER_SUB, "EVENT_OWNER")
ADMIN = bearer(ADMIN_SUB, "ADMIN")
CLIENT = bearer(CLIENT_SUB, "CLIENT")


def client() -> TestClient:
    """A fresh app with its own in-memory store and a fixed clock."""
    unit_of_work = FakeUnitOfWork()
    return TestClient(create_app(ReachableProbe(), uow_factory=lambda: unit_of_work, clock=lambda: NOW))


def event_body(**changes: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "title": "Noche de Tango en el Puerto",
        "description": "Tango de orquesta a orillas del río.",
        "type": "CONCERT",
        "organizer_name": "Orquesta Típica Malvón",
        "participants": [{"name": "Orquesta Típica Malvón"}, {"name": "Lucía Ríos"}],
        "starts_at": (NOW + timedelta(days=30)).isoformat(),
        "venue": {"name": "Teatro del Lago", "city": "Rosario"},
        "zones": [
            {"code": "PLATEA", "name": "Platea", "modality": "NUMBERED", "seat_count": 3},
            {"code": "CAMPO", "name": "Campo", "modality": "UNNUMBERED", "capacity": 8000},
        ],
    }
    body.update(changes)
    return body


def with_key(headers: dict[str, str]) -> dict[str, str]:
    return {**headers, "Idempotency-Key": str(uuid4())}


def create(test_client: TestClient, headers: dict[str, str] = OWNER, **changes: Any) -> dict[str, Any]:
    response = test_client.post("/manage/events", json=event_body(**changes), headers=with_key(headers))
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


def publish(test_client: TestClient, event_id: str, headers: dict[str, str] = OWNER) -> dict[str, Any]:
    response = test_client.post(f"/manage/events/{event_id}/publish", headers=headers)
    assert response.status_code == 200, response.text
    published: dict[str, Any] = response.json()
    return published


def error_fields(response_body: dict[str, Any]) -> set[str]:
    """The field names of a 422 body, from FastAPI's `detail[].loc` without its first element."""
    return {".".join(str(part) for part in item["loc"][1:]) for item in response_body["detail"]}
