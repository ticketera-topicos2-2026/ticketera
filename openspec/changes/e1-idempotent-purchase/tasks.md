# Tasks

Implementation tasks for `e1-idempotent-purchase` (PLAN 7.3, Core Domain).

Follows strict TDD: commit a failing `test(...)` before the `feat(...)` or `fix(...)` that makes it pass (RB-12).
All lint, type checks, and tests run inside Docker containers (D-12).

## 1. Domain Model and Invariants (TDD)

- [ ] 1.1 `test(sales): require domain entities, money value object, and import purity`
  - Test `Seat`, `SeatStatus` (AVAILABLE, SOLD), `Order`, `OrderStatus` (CONFIRMED), `Ticket`, `Money` (ARS centavos).
  - Invariants: cannot sell unavailable seat, non-empty and unique seat IDs in purchase, non-negative money.
  - Test architectural import purity: verify `sales/domain/` imports only standard library modules.
- [ ] 1.2 `feat(sales): implement domain entities and value objects`
  - Pure Python in `services/sales/src/sales/domain/` with zero external dependencies.

## 2. Application Layer, Ports and Use Cases (TDD)

- [ ] 2.1 `test(sales): require application use cases and repository ports`
  - Ports: `InventoryRepository`, `OrderRepository`, `IdempotencyStore`.
  - Use cases: `InitializeInventory`, `GetAvailableSeats`, `PurchaseTickets`, `GetOrder` (with customer authorization).
  - Unit tests using in-memory fake adapters, including BOLA authorization checks.
- [ ] 2.2 `feat(sales): implement application use cases and ports`
  - Application logic in `services/sales/src/sales/application/`.

## 3. Database Persistence, Alembic and Concurrency (TDD)

- [ ] 3.1 `test(sales): require Alembic migrations and database schema`
  - Test migration scripts create tables: `seats`, `orders`, `tickets` with `UNIQUE(event_id, seat_id)`, and `idempotency_keys` with `PRIMARY KEY (customer_id, key)`.
  - Verify container startup automatically runs migrations (`alembic upgrade head`).
- [ ] 3.2 `feat(sales): initialize Alembic and create database schema migrations`
  - Configure `alembic/` in `services/sales/` and update compose entry.
- [ ] 3.3 `test(sales): require SQLAlchemy repositories with ordered row locking and idempotency persistence`
  - Test `SELECT ... FOR UPDATE ORDER BY seat_id` deadlock prevention and concurrency protection in Docker.
  - Test customer-scoped idempotency key storage and concurrent key collision handling.
  - Test autonomy: sales repository functions when catalog is unavailable.
- [ ] 3.4 `feat(sales): implement SQLAlchemy repository adapters`
  - Concrete adapters in `services/sales/src/sales/infrastructure/`.

## 4. API Endpoints, Idempotency Middleware and Claims (TDD)

- [ ] 4.1 `test(sales): require REST endpoints for inventory and idempotent purchases`
  - Test `POST /events/{event_id}/inventory` (Admin role, 401 unauthenticated, 403 forbidden).
  - Test `GET /events/{event_id}/seats` (Available seats).
  - Test `POST /events/{event_id}/orders` with `Idempotency-Key` (Client purchase, duplicate replay, 422 payload mismatch, 422 empty/duplicate seats).
  - Test `GET /orders/{order_id}` with BOLA protection (404 on other customer's order).
- [ ] 4.2 `feat(sales): implement REST controllers, Pydantic schemas, and token claims`
  - Routers in `services/sales/src/sales/api/`.
  - Token claims decoding helper (`sub` as customer_id, role validation).

## 5. Bruno API Test Collection and Contract Tests (D-24)

- [ ] 5.1 `test(sales): add Bruno API test collection`
  - Automated collection in `tests/api/sales/` covering inventory, purchase, idempotency replay, and error scenarios against the Gateway.

## 6. Frontend Purchase Screen (React + shadcn/ui)

- [ ] 6.1 `test(frontend): require seat selector grid, cart summary, and purchase flow`
  - Vitest + React Testing Library tests for `/events/:eventId/buy` and `/orders/:orderId`.
  - Test seat selection, price calculation in ARS, idempotency key generation, and purchase submission.
- [ ] 6.2 `feat(frontend): implement seat selection grid and order confirmation views`
  - React components with Tailwind CSS and shadcn/ui.
  - Routing and API integration with `/api/sales`.

## 7. ADRs and Documentation

- [ ] 7.1 `docs(sales): add ADR-0008 (Payment in Stage II - D-25)`
  - `docs/adr/adr-0008-pago-en-la-etapa-ii.md`
- [ ] 7.2 `docs(sales): add ADR-0009 (Concurrency and Idempotency on PostgreSQL - D-30)`
  - `docs/adr/adr-0009-concurrencia-e-idempotencia-postgresql.md`
- [ ] 7.3 `docs(sales): add ADR-0010 (API and Contract Testing with Bruno - D-24)`
  - `docs/adr/adr-0010-tests-de-api-y-contrato.md`
- [ ] 7.4 `docs(sales): update AGENTS.md with reference hexagonal service conventions (D-33)`
- [ ] 7.5 `docs(sales): record weekly log and update plan status`
