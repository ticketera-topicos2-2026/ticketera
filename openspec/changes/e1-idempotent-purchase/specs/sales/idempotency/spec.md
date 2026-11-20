# Spec Delta

## Purpose

Defines the idempotency mechanism for ticket purchases in `sales`, guaranteeing customer-scoped deduplication,
safe concurrent key collision handling, and replay without duplication.

## ADDED Requirements

### Requirement: Idempotency-Key header is mandatory for purchase requests

The `sales` service MUST require a valid UUIDv4 `Idempotency-Key` header on all order creation endpoints
(`POST /api/sales/events/{event_id}/orders`).

#### Scenario: Purchase request without Idempotency-Key header

- **WHEN** a client sends `POST /api/sales/events/evt-100/orders` without an `Idempotency-Key` header
- **THEN** the response is `400 Bad Request` with an error message stating that `Idempotency-Key` is required

#### Scenario: Purchase request with invalid Idempotency-Key format

- **WHEN** a client sends an `Idempotency-Key` header that is not a valid UUID format
- **THEN** the response is `400 Bad Request` with an error indicating invalid key format

### Requirement: Replay of identical idempotent requests scoped per customer

When the `sales` service receives a purchase request with an `Idempotency-Key` that has already been processed with
an identical payload and the same `customer_id`, it SHALL return the exact stored HTTP response without
re-executing the purchase or issuing additional tickets.

#### Scenario: Client retries after network timeout

- **WHEN** client `usr-10` submits a purchase request with `Idempotency-Key: 9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d`
  that successfully created order `ord-123`, and later sends the exact same request with the same key
- **THEN** the response is `201 Created` returning order `ord-123` with the original tickets, and no new order or
  tickets are created in the database

### Requirement: Customer isolation for idempotency keys

The `sales` service SHALL scope idempotency keys per customer using a composite primary key `(customer_id, key)`,
preventing cross-customer key collisions or data leaks.

#### Scenario: Different customers use the same idempotency key

- **WHEN** customer `usr-10` completes an order using `Idempotency-Key: 9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d`,
  and customer `usr-20` submits a purchase request with the exact same key for different seats
- **THEN** customer `usr-20`'s purchase is processed independently as a new order, without seeing or colliding
  with `usr-10`'s order

### Requirement: Concurrent identical requests with the same key

When two concurrent requests from the same customer arrive simultaneously with the same new `Idempotency-Key`,
the `sales` service SHALL serialize them via PostgreSQL row locks on `idempotency_keys`: the second transaction
waits for the first to commit, reads the confirmed response, and returns the identical `201 Created` replay
without polling or re-executing business logic.

#### Scenario: Simultaneous double-click with identical key

- **WHEN** a client simultaneously submits two identical purchase requests with the same new `Idempotency-Key`
- **THEN** exactly one order is created in the database, and both requests receive identical `201 Created`
  responses with the same order and tickets

### Requirement: Conflict on mismatched payload with same key

If a request from the same customer arrives with an `Idempotency-Key` that was already completed but with a
different request payload (e.g. different seats or event), the `sales` service SHALL reject it with `422 Unprocessable Entity`.

#### Scenario: Reusing an idempotency key with different seats

- **WHEN** a client sends a purchase request using a previously completed `Idempotency-Key` but requesting
  different seat identifiers
- **THEN** the response is `422 Unprocessable Entity` indicating an idempotency key payload mismatch

### Requirement: Transactional atomicity of idempotency key persistence

The idempotency record MUST be committed to `sales_db` in the same database transaction as the order and ticket
creation (D-30).

#### Scenario: Purchase transaction failure rolls back idempotency key

- **WHEN** a database constraint fails during order creation
- **THEN** the entire transaction rolls back, no order is saved, and the `Idempotency-Key` is not persisted,
  allowing clean future attempts with the same key
