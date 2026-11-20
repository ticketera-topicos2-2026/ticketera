# Spec Delta

## Purpose

Defines the core ticket purchase capability in `sales`: seat selection, order confirmation, and ticket issuance in
a single atomic transaction without a payment gateway step in Stage I (D-25), with deadlock prevention, duplicate
seat rejection, OWASP BOLA protection, and complete token claims enforcement from the gateway perimeter.

## ADDED Requirements

### Requirement: Atomic ticket purchase and issuance

When an authenticated client with `CLIENT` role submits a valid purchase request for available seats with an
idempotency key, the `sales` service SHALL mark the seats as `SOLD`, create an `Order` with status `CONFIRMED`, and
issue unique `Ticket` records linked to the order within a single database transaction.

#### Scenario: Successful purchase of available seats

- **WHEN** an authenticated user with `CLIENT` role and `sub: usr-10` sends `POST /api/sales/events/evt-100/orders`
  with seats `["A-1", "A-2"]` and a valid `Idempotency-Key` header
- **THEN** the response is `201 Created`, the order status is `CONFIRMED` with `customer_id: usr-10`, two tickets
  with unique alphanumeric codes are returned linked to `ord-123`, and seats `A-1` and `A-2` are marked `SOLD`

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

### Requirement: Services take roles only from the platform roles in realm_access.roles

The `sales` service SHALL treat a user as holding only those of `ADMIN`, `EVENT_OWNER` and `CLIENT` that appear in the
token's `realm_access.roles` claim. It SHALL ignore every other role in that claim and any role found in any
other claim.

#### Scenario: Default roles of the identity service

- **WHEN** `sales` receives a token whose `realm_access.roles` contains `CLIENT`, `offline_access`,
  `uma_authorization` and `default-roles-ticketera`
- **THEN** the service treats the user as holding only the `CLIENT` role

#### Scenario: Role in another claim

- **WHEN** `sales` receives a token whose `realm_access.roles` contains only `CLIENT` and whose other claims
  mention `ADMIN`
- **THEN** the service does not treat the user as holding the `ADMIN` role

#### Scenario: Token without realm roles

- **WHEN** `sales` receives a token with no `realm_access.roles` claim
- **THEN** the service treats the user as holding no platform role

### Requirement: Services identify the user only from the token

The `sales` service SHALL take the user's identity and roles only from the bearer token in the `Authorization` header, and
SHALL ignore any user identity or role that the client sends in another header, the query string or the body.
`sales` SHALL key customer data (such as orders and idempotency keys) by `sub`.

#### Scenario: Forged identity header

- **WHEN** the `CLIENT` test user sends a request with its token and an `X-User-Id` header naming another user
- **THEN** the service handles the request as the user identified by the token's `sub`

#### Scenario: Forged role in the body

- **WHEN** the `CLIENT` test user sends a request with its token and a body that claims the `ADMIN` role
- **THEN** the service handles the request as a user holding only the `CLIENT` role

### Requirement: Services trust the token validated by the gateway

The `sales` service SHALL read the claims of a bearer token by decoding its payload, relying on the gateway having
validated the token, without checking its signature or calling the identity service. It SHALL answer
`401 Unauthorized` when the payload cannot be decoded.

#### Scenario: Valid token forwarded by the gateway

- **WHEN** `sales` receives a request with a token that the gateway has validated
- **THEN** the service reads `sub` and `realm_access.roles` from it without any request to the identity service

#### Scenario: Payload that cannot be decoded

- **WHEN** `sales` receives a request to a protected endpoint whose bearer token has a payload that is not
  valid JSON
- **THEN** the service answers `401 Unauthorized` and performs no operation

### Requirement: Services never expose or accept tokens outside the Authorization header

The `sales` service MUST NOT write the `Authorization` header or any token to its logs, and MUST NOT accept a token from the
query string.

#### Scenario: Request with a token is logged

- **WHEN** `sales` handles a request with a bearer token
- **THEN** no line the service writes to its logs contains the token

#### Scenario: Token in the query string

- **WHEN** a request to a protected endpoint carries a token only in its query string
- **THEN** the service answers `401 Unauthorized` and performs no operation
