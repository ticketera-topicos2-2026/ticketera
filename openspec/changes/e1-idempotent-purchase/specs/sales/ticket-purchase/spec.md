# Spec Delta

## Purpose

Defines the core ticket purchase capability in `sales`: seat selection, order confirmation, and ticket issuance in
a single atomic transaction without a payment gateway step in Stage I (D-25), with deadlock prevention, duplicate
seat rejection, and OWASP BOLA protection.

## ADDED Requirements

### Requirement: Atomic ticket purchase and issuance

When an authenticated client with `CLIENT` role submits a valid purchase request for available seats with an
idempotency key, the `sales` service SHALL mark the seats as `SOLD`, create an `Order` with status `CONFIRMED`, and
issue unique `Ticket` records linked to the order within a single database transaction.

#### Scenario: Successful purchase of available seats

- **WHEN** an authenticated user with `CLIENT` role and `sub: usr-10` sends `POST /api/sales/events/evt-100/orders`
  with seats `["A-1", "A-2"]` and a valid `Idempotency-Key` header
- **THEN** the response is `201 Created`, the order status is `CONFIRMED`, two tickets with unique alphanumeric
  codes are returned, and seats `A-1` and `A-2` are marked `SOLD` with `customer_id: usr-10`

#### Scenario: Unauthenticated purchase rejected

- **WHEN** an unauthenticated request sends `POST /api/sales/events/evt-100/orders` without credentials
- **THEN** the response is `401 Unauthorized`

#### Scenario: Non-client role purchase rejected

- **WHEN** an authenticated user holding only `EVENT_OWNER` or `ADMIN` role sends `POST /api/sales/events/evt-100/orders`
- **THEN** the response is `403 Forbidden`

### Requirement: Strict prevention of double-selling

The `sales` service SHALL reject any purchase request that includes one or more seats that are not in `AVAILABLE`
status, ensuring all-or-nothing atomicity.

#### Scenario: Purchase request with an already sold seat

- **WHEN** seat `A-1` is `SOLD` and a client attempts to purchase `["A-1", "A-2"]`
- **THEN** the response is `409 Conflict`, the order is rejected, and seat `A-2` remains `AVAILABLE`

#### Scenario: Concurrent purchase of the same seat

- **WHEN** two concurrent requests attempt to purchase seat `A-1` at the exact same moment
- **THEN** exactly one request succeeds with `201 Created` and the other fails with `409 Conflict`

### Requirement: Deadlock prevention and seat payload validation

The `sales` service SHALL acquire row locks on seats strictly ordered by `seat_id` (`ORDER BY seat_id`), and SHALL
reject purchase requests with duplicate or empty seat lists.

#### Scenario: Empty seat list rejected

- **WHEN** a client sends `POST /api/sales/events/evt-100/orders` with `seat_ids: []`
- **THEN** the response is `422 Unprocessable Entity`

#### Scenario: Duplicate seats in request rejected

- **WHEN** a client sends `POST /api/sales/events/evt-100/orders` with `seat_ids: ["A-1", "A-1"]`
- **THEN** the response is `422 Unprocessable Entity`

### Requirement: Retrieve confirmed order details with BOLA protection

The `sales` service SHALL allow a client to retrieve their confirmed order by its `order_id`, and SHALL reject
access to orders owned by other customers (OWASP API1 / BOLA).

#### Scenario: Client queries their own order

- **WHEN** an authenticated client with `sub: usr-10` sends `GET /api/sales/orders/{order_id}` for an order
  belonging to `usr-10`
- **THEN** the response is `200 OK` with order details and issued tickets

#### Scenario: Client queries another customer's order (BOLA protection)

- **WHEN** an authenticated client with `sub: usr-20` sends `GET /api/sales/orders/{order_id}` for an order
  belonging to `usr-10`
- **THEN** the response is `404 Not Found`

#### Scenario: Admin queries any customer's order

- **WHEN** an authenticated user with `ADMIN` role sends `GET /api/sales/orders/{order_id}` for an order
  belonging to `usr-10`
- **THEN** the response is `200 OK` with order details

#### Scenario: Query nonexistent order

- **WHEN** a client sends `GET /api/sales/orders/{nonexistent_id}`
- **THEN** the response is `404 Not Found`
