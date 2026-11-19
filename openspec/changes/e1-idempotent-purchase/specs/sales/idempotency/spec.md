# Spec Delta

## Purpose

Defines the idempotency mechanism for ticket purchases in `sales`, guaranteeing that network retries or duplicate
client submissions never produce duplicate orders or multiple tickets.

## ADDED Requirements

### Requirement: Idempotency-Key header is mandatory for purchase requests

The `sales` service MUST require a valid UUIDv4 `Idempotency-Key` header on all order creation endpoints
(`POST /api/sales/events/{event_id}/orders`).

#### Scenario: Purchase request without Idempotency-Key header

- **WHEN** a client sends `POST /api/sales/events/evt-100/orders` without an `Idempotency-Key` header
- **THEN** the response is `400 Bad Request` with an error message stating that `Idempotency-Key` is required

#### Scenario: Purchase request with invalid Idempotency-Key format

- **WHEN** a client sends an `Idempotency-Key` header that is not a valid UUID format (e.g. `12345`)
- **THEN** the response is `400 Bad Request` with an error indicating invalid key format

### Requirement: Replay of identical idempotent requests

When the `sales` service receives a purchase request with an `Idempotency-Key` that has already been processed with
an identical payload and client identity, it SHALL return the exact stored HTTP response without re-executing
the purchase or issuing additional tickets.

#### Scenario: Client retries after network timeout

- **WHEN** a client submits a purchase request with `Idempotency-Key: 9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d` that
  successfully created order `ord-123`, and later sends the exact same request with the same key
- **THEN** the response is `201 Created` returning order `ord-123` with the original tickets, and no new order or
  tickets are created in the database

### Requirement: Conflict on mismatched payload with same key

If a request arrives with an `Idempotency-Key` that was already used with a different request payload (e.g.
different seats or event), the `sales` service SHALL reject it.

#### Scenario: Reusing an idempotency key with different seats

- **WHEN** a client sends a purchase request using a previously completed `Idempotency-Key` but requesting
  different seat identifiers
- **THEN** the response is `422 Unprocessable Entity` or `409 Conflict` indicating an idempotency key payload
  mismatch

### Requirement: Transactional atomicity of idempotency key persistence

The idempotency record MUST be committed to `sales_db` in the same database transaction as the order and ticket
creation (D-30).

#### Scenario: Purchase transaction failure rolls back idempotency key

- **WHEN** a database constraint fails during order creation
- **THEN** the entire transaction rolls back, no order is saved, and the `Idempotency-Key` is not persisted,
  allowing clean future attempts with the same key
