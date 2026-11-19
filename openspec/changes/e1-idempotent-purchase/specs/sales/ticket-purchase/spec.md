# Spec Delta

## Purpose

Defines the core ticket purchase capability in `sales`: selecting seats, reserving them, confirming the order, and
issuing tickets in a single atomic transaction without a payment gateway step in Stage I (D-25).

## ADDED Requirements

### Requirement: Atomic ticket purchase and issuance

When a client submits a valid purchase request for available seats with an idempotency key, the `sales` service
SHALL mark the seats as `SOLD`, create an `Order` with status `CONFIRMED`, and issue unique `Ticket` records within
a single database transaction.

#### Scenario: Successful purchase of available seats

- **WHEN** a client sends `POST /api/sales/events/evt-100/orders` with seats `["A-1", "A-2"]` and a valid
  `Idempotency-Key` header
- **THEN** the response is `201 Created`, the order status is `CONFIRMED`, two tickets with unique alphanumeric
  codes are returned, and seats `A-1` and `A-2` are marked `SOLD`

### Requirement: Strict prevention of double-selling

The `sales` service SHALL reject any purchase request that includes one or more seats that are not in `AVAILABLE`
status, ensuring all-or-nothing atomicity.

#### Scenario: Purchase request with an already sold seat

- **WHEN** seat `A-1` is `SOLD` and a client attempts to purchase `["A-1", "A-2"]`
- **THEN** the response is `409 Conflict`, the order is rejected, and seat `A-2` remains `AVAILABLE`

#### Scenario: Concurrent purchase of the same seat

- **WHEN** two concurrent requests attempt to purchase seat `A-1` at the exact same moment
- **THEN** exactly one request succeeds with `201 Created` and the other fails with `409 Conflict`

### Requirement: Retrieve confirmed order details

The `sales` service SHALL allow a client to retrieve their confirmed order by its `order_id`.

#### Scenario: Query existing order

- **WHEN** a client sends `GET /api/sales/orders/{order_id}` for an existing confirmed order
- **THEN** the response is `200 OK` with the order status, total price, and the list of issued tickets

#### Scenario: Query nonexistent order

- **WHEN** a client sends `GET /api/sales/orders/{nonexistent_id}`
- **THEN** the response is `404 Not Found`
