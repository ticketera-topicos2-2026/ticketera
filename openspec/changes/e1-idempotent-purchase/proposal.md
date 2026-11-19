# Proposal

## Why

Stage I focuses on solving the core architectural problem first (PLAN 7.3, D-28): handling concurrent ticket
purchases without overselling, while ensuring strict idempotency against network retries. In the walking skeleton,
`sales` is an empty hexagonal shell that only exposes `/health`. To support ticket sales, `sales` requires a domain
model for inventory and orders, database tables managed through Alembic migrations, atomic state transitions,
PostgreSQL-backed concurrency control (D-30), and an idempotency key store that prevents duplicate orders.

Furthermore, this change establishes the reference hexagonal architecture and service conventions (D-33) that all
other backend microservices will follow throughout Stage I and subsequent stages.

## What Changes

- **Domain Model (`services/sales/src/sales/domain/`)**:
  - Pure Python entities and value objects representing `EventInventory`, `Seat`, `SeatStatus` (`AVAILABLE`, `RESERVED`, `SOLD`), `Order`, `OrderStatus` (`PENDING`, `CONFIRMED`, `EXPIRED`), `Ticket`, and `Money`.
  - Invariants: A seat cannot be reserved or sold if not available; an order cannot be confirmed if its temporary reservation has expired; a ticket is issued strictly upon order confirmation.
  - Zero external dependencies on web frameworks or ORMs.
- **Application Layer (`services/sales/src/sales/application/`)**:
  - Ports (interfaces): `InventoryRepository`, `OrderRepository`, `IdempotencyStore`, and `Clock`.
  - Use cases:
    - `initialize_inventory`: Administrative capability for `ADMIN` to load seat inventory for an `event_id` (using `event_id` as an opaque reference, D-28).
    - `reserve_seats`: Reserve selected seats with a configurable Time-To-Live (TTL) expiration.
    - `purchase_tickets`: Atomic purchase flow that transitions reservations to confirmed orders and issues tickets in a single idempotent request without a payment gateway step (D-25).
  - Domain error definitions mapped to clean application-level exceptions.
- **Infrastructure Layer (`services/sales/src/sales/infrastructure/`)**:
  - SQLAlchemy 2 persistence models and mapped tables.
  - Alembic migrations directory (`services/sales/alembic/`) to manage database schema evolution.
  - Concurrency control via PostgreSQL: Row-level locks (`SELECT ... FOR UPDATE`) or unique constraints on `(event_id, seat_id)` ensuring strict prevention of double-selling without Redis (D-30).
  - Idempotency store table (`idempotency_keys` in `sales_db`) persisting `key`, `client_id`, `request_hash`, `response_status`, and `response_body` within the same database transaction as the order creation (D-30).
- **API Layer (`services/sales/src/sales/api/`)**:
  - HTTP endpoints exposed under `/api/sales`:
    - `POST /events/{event_id}/inventory`: Admin endpoint to initialize seat availability.
    - `POST /events/{event_id}/orders`: Client endpoint to purchase tickets idempotently. Requires header `Idempotency-Key` (UUIDv4) and processes purchases atomically.
    - `GET /orders/{order_id}`: Retrieve order details and issued tickets.
  - Pydantic v2 request/response schemas decoupled from domain entities.
  - Token claims integration: Read `sub` (client ID) and verify role `CLIENT` or `ADMIN` from the perimeter Gateway token claims contract (D-33, D-28). Initial testing supported without authentication, with JWT enforcement wired as gateway integration stabilizes.
- **Service Reference Skeleton (`D-33`)**:
  - Defines the four-layer hexagonal packaging and dependency rules in `AGENTS.md`.
  - Configures Alembic environment for PostgreSQL.
  - Establishes unit, integration, and acceptance testing patterns.
- **Tests**:
  - Unit tests for domain logic and invariants (100% pure Python, fast execution).
  - Integration tests for SQLAlchemy repositories against real PostgreSQL in Docker.
  - API tests via `TestClient` verifying HTTP contracts, idempotency replay on duplicate key, and conflict handling (HTTP 409).
  - Bruno API test collection in `tests/api/sales/` (D-24).
- **Architecture Decision Records (ADRs)**:
  - `docs/adr/adr-0008-pago-en-la-etapa-ii.md` (D-25): Deferring payment processing to Stage II.
  - `docs/adr/adr-0009-concurrencia-e-idempotencia-postgresql.md` (D-30): Concurrency control and idempotency on PostgreSQL without Redis.
  - `docs/adr/adr-0010-tests-de-api-y-contrato.md` (D-24): API testing and contract validation strategy.

## Non-goals

- Payment processing: Handled as a separate Stage II change in `payments` (D-25).
- Redis caching or distributed locks: PostgreSQL provides full ACID guarantees and acts as the sole arbiter of concurrency in Stage I (D-30).
- Asynchronous messaging / RabbitMQ: Event publishing (e.g. `order.confirmed`) is deferred to Stage II integration events.
- Catalog data synchronization: `sales` maintains autonomous inventory and does not read `catalog_db` (ADR-0004).

## Capabilities

### New Capabilities

- `sales/ticket-inventory`: Initializing and querying seat availability for events.
- `sales/ticket-purchase`: Reserving seats, confirming orders, and issuing tickets in a single atomic operation.
- `sales/idempotency`: Deduplicating purchase requests and guaranteeing safe retries via `Idempotency-Key`.
- `platform/service-skeleton`: Establishing the reference hexagonal structure and Alembic migration pattern for microservices (D-33).

## Impact

- **Bounded contexts**: `sales` (Core Domain). No database or direct code changes to `catalog` or `payments`.
- **Owner**: Gustavo (team member C).
- **Code**:
  - `services/sales/src/sales/domain/`
  - `services/sales/src/sales/application/`
  - `services/sales/src/sales/infrastructure/`
  - `services/sales/src/sales/api/`
  - `services/sales/alembic/`
  - `services/sales/tests/`
  - `tests/api/sales/` (Bruno collection)
- **ADRs**: ADR-0008 (D-25), ADR-0009 (D-30), ADR-0010 (D-24).
- **Documentation**: Updates to `AGENTS.md` (D-33 service rules), team log, and `CONTRIBUTE.md`.

