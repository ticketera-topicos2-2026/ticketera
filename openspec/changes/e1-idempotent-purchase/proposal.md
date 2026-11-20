# Proposal

## Why

Stage I focuses on solving the core architectural problem first (PLAN 7.3, D-28): handling concurrent ticket
purchases without overselling, while ensuring strict idempotency against network retries. In the walking skeleton,
`sales` is an empty hexagonal shell that only exposes `/health`. To support ticket sales, `sales` requires a domain
model for inventory, orders, and tickets, database tables managed through Alembic migrations, atomic single-step
purchases without a payment gateway (D-25), PostgreSQL-backed concurrency control (D-30), an idempotency key store
scoped per customer that prevents duplicate orders, and a frontend user interface for selecting and purchasing
tickets (D-28, D-32).

Furthermore, this change establishes the reference hexagonal architecture and service conventions (D-33) that all
other backend microservices will follow throughout Stage I and subsequent stages.

## What Changes

- **Domain Model (`services/sales/src/sales/domain/`)**:
  - Pure Python entities and value objects: `Seat`, `SeatStatus` (`AVAILABLE`, `SOLD`), `Order`, `OrderStatus` (`CONFIRMED`), `Ticket`, and `Money` (integer amount in Argentine Centavos, currency `ARS`).
  - Invariants: A seat cannot be sold if not available; ticket codes are generated upon order creation; seat IDs in a purchase must be non-empty and unique; money values must be non-negative.
  - Zero external dependencies on web frameworks or ORMs.
- **Application Layer (`services/sales/src/sales/application/`)**:
  - Ports (interfaces): `InventoryRepository`, `OrderRepository`, `IdempotencyStore`, and `Clock`.
  - Use cases:
    - `initialize_inventory`: Administrative capability for `ADMIN` to load seat inventory for an `event_id` (using `event_id` as an opaque reference, D-28).
    - `get_available_seats`: Query seats currently available for sale.
    - `purchase_tickets`: Atomic purchase flow that validates availability, transitions seats from `AVAILABLE` to `SOLD`, creates a confirmed order, and issues tickets in a single idempotent request without a payment gateway step (D-25).
    - `get_order`: Retrieve order details and issued tickets, enforcing access control (clients can only view their own orders, OWASP BOLA).
  - Domain error definitions mapped to clean application-level exceptions.
- **Infrastructure Layer (`services/sales/src/sales/infrastructure/`)**:
  - SQLAlchemy 2 persistence models and mapped tables (`seats`, `orders`, `tickets`, `idempotency_keys`).
  - Strict constraints: Composite primary key `(customer_id, key)` for `idempotency_keys`; `UNIQUE (event_id, seat_id)` constraint on `tickets` as an extra persistence guarantee against double assignment.
  - Alembic migrations directory (`services/sales/alembic/`) to manage database schema evolution. Container startup automatically applies migrations (`alembic upgrade head`).
  - Concurrency control via PostgreSQL: Ordered row-level locks (`SELECT ... FOR UPDATE ORDER BY seat_id`) to prevent deadlocks and race conditions, ensuring strict prevention of double-selling without Redis (D-30).
  - Idempotency store table (`idempotency_keys` in `sales_db`) with status tracking (`IN_PROGRESS`, `COMPLETED`), persisting `key`, `customer_id`, `request_hash`, `response_status`, and `response_body` within the database transaction (D-30).
- **API Layer (`services/sales/src/sales/api/`)**:
  - HTTP endpoints exposed under `/api/sales`:
    - `POST /events/{event_id}/inventory`: Admin endpoint to initialize seat availability. Requires `ADMIN` role.
    - `GET /events/{event_id}/seats`: Query available seats.
    - `POST /events/{event_id}/orders`: Client endpoint to purchase tickets idempotently. Requires `CLIENT` role and `Idempotency-Key` (UUIDv4) header.
    - `GET /orders/{order_id}`: Retrieve order details. Accessible to `ADMIN` or the owning `CLIENT` (`sub` matching `customer_id`).
  - Pydantic v2 request/response schemas decoupled from domain entities.
  - Token claims integration: Read `sub` as `customer_id` and verify role `CLIENT` or `ADMIN` from the perimeter Gateway token claims contract (D-33, D-28). Initial local testing supported without authentication, with JWT enforcement wired as gateway integration stabilizes.
- **Frontend (`frontend/src/`)**:
  - Ticket purchase screen under `/events/:eventId/buy` and order confirmation view under `/orders/:orderId`.
  - Built with Tailwind CSS and shadcn/ui components (D-16).
  - Seat selection grid displaying available seats, price summary, and purchase confirmation button with client-generated `Idempotency-Key` (UUIDv4).
  - Component mockups and unit/integration tests with Vitest and React Testing Library (D-16).
- **Service Reference Skeleton (`D-33`)**:
  - Defines the four-layer hexagonal packaging and dependency rules in `AGENTS.md`.
  - Configures Alembic environment for PostgreSQL.
  - Establishes unit, integration, and acceptance testing patterns.
- **Tests**:
  - Unit tests for domain logic, invariants, and architectural import purity.
  - Integration tests for SQLAlchemy repositories against real PostgreSQL in Docker.
  - API tests via `TestClient` verifying HTTP contracts, idempotency replay, concurrent key collisions, payload mismatch (`422`), BOLA protection (`404`), and role enforcement (`401`/`403`).
  - Contract and isolation tests: verifying `sales` functions when `catalog` is stopped.
  - Bruno API test collection in `tests/api/sales/` (D-24).
- **Architecture Decision Records (ADRs)**:
  - `docs/adr/adr-0008-pago-en-la-etapa-ii.md` (D-25): Deferring payment processing to Stage II.
  - `docs/adr/adr-0009-concurrencia-e-idempotencia-postgresql.md` (D-30): Concurrency control and idempotency on PostgreSQL without Redis.
  - `docs/adr/adr-0010-tests-de-api-y-contrato.md` (D-24): API testing and contract validation strategy.

## Non-goals

- Payment processing: Handled as a separate Stage II change in `payments` (D-25).
- Redis caching or distributed locks: PostgreSQL provides full ACID guarantees and acts as the sole arbiter of concurrency in Stage I (D-30).
- RabbitMQ messaging: Event publishing (e.g. `order.confirmed`) is deferred to Stage II integration events.
- Catalog data synchronization: `sales` maintains autonomous inventory and does not read `catalog_db` (ADR-0004).

## Capabilities

### New Capabilities

- `sales/ticket-inventory`: Initializing and querying seat availability for events.
- `sales/ticket-purchase`: Reserving seats, confirming orders, and issuing tickets in a single atomic operation with BOLA protection.
- `sales/idempotency`: Customer-scoped request deduplication and safe retries via `Idempotency-Key`.
- `platform/service-skeleton`: Establishing the reference hexagonal structure and Alembic migration pattern for microservices (D-33).

## Impact

- **Bounded contexts**: `sales` (Core Domain) and `frontend`. No database or direct code changes to `catalog` or `payments`.
- **Owner**: Integrante C (@gustavoandresfu).
- **Code**:
  - `services/sales/src/sales/domain/`
  - `services/sales/src/sales/application/`
  - `services/sales/src/sales/infrastructure/`
  - `services/sales/src/sales/api/`
  - `services/sales/alembic/`
  - `services/sales/tests/`
  - `frontend/src/` (seat selection, purchase screen, order view)
  - `tests/api/sales/` (Bruno collection)
- **ADRs**: ADR-0008 (D-25), ADR-0009 (D-30), ADR-0010 (D-24).
- **Documentation**: Updates to `AGENTS.md` (D-33 service rules), team log, and `CONTRIBUTE.md`.
