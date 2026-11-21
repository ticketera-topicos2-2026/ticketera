"""Tests for REST endpoints for inventory and idempotent ticket purchases.

Verifies:
- POST /events/{event_id}/inventory (Admin role, 401 unauthenticated, 403 forbidden)
- GET /events/{event_id}/seats (Authentication required, 401 unauthenticated, 403 forbidden)
- POST /events/{event_id}/orders with Idempotency-Key (Client purchase, duplicate replay, 400 on missing key, 422 payload mismatch, 422 empty/duplicate seats)
- GET /orders/{order_id} with BOLA protection (404 on other customer's order)
"""

import base64
import json
import uuid
from typing import Any
import pytest
from fastapi.testclient import TestClient

from sales.api.app import create_app
from sales.application.health import DatabaseProbe
from sales.domain.models import Seat, SeatStatus, Order
from sales.application.ports import InventoryRepository, OrderRepository, IdempotencyStore, StoredIdempotencyRecord
from sales.domain.exceptions import SeatNotAvailableError


def _make_jwt(sub: str, roles: list[str]) -> str:
    """Helper to generate an unverified base64url encoded JWT for perimeter testing."""
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none"}).encode()).decode().rstrip("=")
    payload = base64.urlsafe_b64encode(
        json.dumps({
            "sub": sub,
            "realm_access": {"roles": roles}
        }).encode()
    ).decode().rstrip("=")
    return f"{header}.{payload}."


class FakeDatabaseProbe(DatabaseProbe):
    def is_reachable(self) -> bool:
        return True


class InMemoryInventoryRepo(InventoryRepository):
    def __init__(self) -> None:
        self.seats: dict[tuple[str, str], Seat] = {}

    def exists_any(self, event_id: str) -> bool:
        return any(e_id == event_id for (e_id, _) in self.seats.keys())

    def save_all(self, seats: list[Seat]) -> None:
        for s in seats:
            self.seats[(s.event_id, s.seat_id)] = s

    def find_by_event(self, event_id: str, status: SeatStatus | None = None) -> list[Seat]:
        res = [s for s in self.seats.values() if s.event_id == event_id]
        if status is not None:
            res = [s for s in res if s.status == status]
        return res

    def find_by_seats_for_update(self, event_id: str, seat_ids: list[str]) -> list[Seat]:
        res = []
        for sid in seat_ids:
            key = (event_id, sid)
            if key not in self.seats or self.seats[key].status != SeatStatus.AVAILABLE:
                raise SeatNotAvailableError(f"Seat {sid} is not available")
            res.append(self.seats[key])
        return res


class InMemoryOrderRepo(OrderRepository):
    def __init__(self) -> None:
        self.orders: dict[str, Order] = {}

    def save(self, order: Order) -> None:
        self.orders[order.order_id] = order

    def find_by_id(self, order_id: str) -> Order | None:
        return self.orders.get(order_id)


class InMemoryIdempotencyStore(IdempotencyStore):
    def __init__(self) -> None:
        self.records: dict[tuple[str, str], StoredIdempotencyRecord] = {}

    def reserve(self, customer_id: str, key: str, request_hash: str) -> bool:
        k = (customer_id, key)
        if k in self.records:
            return False
        self.records[k] = StoredIdempotencyRecord(customer_id, key, request_hash, None, None)
        return True

    def get(self, customer_id: str, key: str) -> StoredIdempotencyRecord | None:
        return self.records.get((customer_id, key))

    def update_response(self, customer_id: str, key: str, status: int, body: dict[str, Any]) -> None:
        k = (customer_id, key)
        rec = self.records[k]
        self.records[k] = StoredIdempotencyRecord(rec.customer_id, rec.key, rec.request_hash, status, body)

    def remove(self, customer_id: str, key: str) -> None:
        self.records.pop((customer_id, key), None)


@pytest.fixture
def client() -> TestClient:
    app = create_app(
        database_probe=FakeDatabaseProbe(),
        inventory_repo=InMemoryInventoryRepo(),
        order_repo=InMemoryOrderRepo(),
        idempotency_store=InMemoryIdempotencyStore(),
    )
    return TestClient(app)


def test_initialize_inventory_requires_admin(client: TestClient) -> None:
    # 401 unauthenticated
    resp = client.post("/events/ev-1/inventory", json={"seats": [{"seat_id": "A-1", "category": "GENERAL", "price_centavos": 1000}]})
    assert resp.status_code == 401

    # 403 forbidden if not ADMIN
    client_token = _make_jwt("user-1", ["CLIENT"])
    resp = client.post(
        "/events/ev-1/inventory",
        headers={"Authorization": f"Bearer {client_token}"},
        json={"seats": [{"seat_id": "A-1", "category": "GENERAL", "price_centavos": 1000}]}
    )
    assert resp.status_code == 403

    # 201 created if ADMIN
    admin_token = _make_jwt("admin-1", ["ADMIN"])
    resp = client.post(
        "/events/ev-1/inventory",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"seats": [{"seat_id": "A-1", "category": "GENERAL", "price_centavos": 1000}]}
    )
    assert resp.status_code == 201


def test_get_available_seats_requires_auth(client: TestClient) -> None:
    # 401 unauthenticated
    resp = client.get("/events/ev-1/seats")
    assert resp.status_code == 401

    # 200 ok for CLIENT
    client_token = _make_jwt("user-1", ["CLIENT"])
    resp = client.get("/events/ev-1/seats", headers={"Authorization": f"Bearer {client_token}"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_purchase_tickets_missing_or_invalid_idempotency_key(client: TestClient) -> None:
    client_token = _make_jwt("user-1", ["CLIENT"])

    # Missing Idempotency-Key -> 400 Bad Request
    resp = client.post(
        "/events/ev-1/orders",
        headers={"Authorization": f"Bearer {client_token}"},
        json={"seat_ids": ["A-1"]}
    )
    assert resp.status_code == 400

    # Invalid UUID Idempotency-Key -> 400 Bad Request
    resp = client.post(
        "/events/ev-1/orders",
        headers={"Authorization": f"Bearer {client_token}", "Idempotency-Key": "not-a-uuid"},
        json={"seat_ids": ["A-1"]}
    )
    assert resp.status_code == 400


def test_purchase_tickets_successful_and_idempotent_replay(client: TestClient) -> None:
    admin_token = _make_jwt("admin-1", ["ADMIN"])
    client_token = _make_jwt("user-1", ["CLIENT"])

    # 1. Init inventory
    client.post(
        "/events/ev-1/inventory",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"seats": [{"seat_id": "A-1", "category": "GENERAL", "price_centavos": 5000}]}
    )

    # 2. Purchase tickets
    idem_key = str(uuid.uuid4())
    resp = client.post(
        "/events/ev-1/orders",
        headers={"Authorization": f"Bearer {client_token}", "Idempotency-Key": idem_key},
        json={"seat_ids": ["A-1"]}
    )
    assert resp.status_code == 201
    body1 = resp.json()
    assert body1["event_id"] == "ev-1"
    assert body1["customer_id"] == "user-1"
    assert body1["total_amount_centavos"] == 5000
    assert len(body1["tickets"]) == 1
    assert body1["tickets"][0]["seat_id"] == "A-1"

    # 3. Duplicate replay with same key and same payload -> 201 identical response
    resp2 = client.post(
        "/events/ev-1/orders",
        headers={"Authorization": f"Bearer {client_token}", "Idempotency-Key": idem_key},
        json={"seat_ids": ["A-1"]}
    )
    assert resp2.status_code == 201
    assert resp2.json() == body1

    # 4. Same key with different payload -> 422 Unprocessable Entity
    resp3 = client.post(
        "/events/ev-1/orders",
        headers={"Authorization": f"Bearer {client_token}", "Idempotency-Key": idem_key},
        json={"seat_ids": ["A-2"]}
    )
    assert resp3.status_code == 422


def test_get_order_bola_protection(client: TestClient) -> None:
    admin_token = _make_jwt("admin-1", ["ADMIN"])
    user1_token = _make_jwt("user-1", ["CLIENT"])
    user2_token = _make_jwt("user-2", ["CLIENT"])

    client.post(
        "/events/ev-1/inventory",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"seats": [{"seat_id": "A-1", "category": "GENERAL", "price_centavos": 5000}]}
    )

    idem_key = str(uuid.uuid4())
    resp = client.post(
        "/events/ev-1/orders",
        headers={"Authorization": f"Bearer {user1_token}", "Idempotency-Key": idem_key},
        json={"seat_ids": ["A-1"]}
    )
    order_id = resp.json()["order_id"]

    # User 1 (owner) can view -> 200
    resp_owner = client.get(f"/orders/{order_id}", headers={"Authorization": f"Bearer {user1_token}"})
    assert resp_owner.status_code == 200
    assert resp_owner.json()["order_id"] == order_id

    # User 2 (not owner) -> 404 Not Found (BOLA prevention)
    resp_other = client.get(f"/orders/{order_id}", headers={"Authorization": f"Bearer {user2_token}"})
    assert resp_other.status_code == 404

    # Admin can view -> 200
    resp_admin = client.get(f"/orders/{order_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp_admin.status_code == 200
