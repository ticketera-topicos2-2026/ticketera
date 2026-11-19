# Tasks

Implementation tasks for `e1-idempotent-purchase` (PLAN 7.3, Core Domain).

Follows strict TDD: commit a failing `test(...)` before the `feat(...)` or `fix(...)` that makes it pass (RB-12).
All lint, type checks, and tests run inside Docker containers (D-12).

## 1. Domain Model and Invariants (TDD)

- [ ] 1.1 `test(sales): require domain entities and value objects for inventory, orders, and tickets`
  - Seat, SeatStatus (AVAILABLE, RESERVED, SOLD), Money, Order, OrderStatus, Ticket.
  - Test invariants: cannot reserve unavailable seat, cannot confirm expired order, ticket code generation.
- [ ] 1.2 `feat(sales): implement domain entities and value objects`
  - Pure Python in `services/sales/src/sales/domain/` with zero external dependencies.

## 2. Application Layer, Ports and Use Cases (TDD)

- [ ] 2.1 `test(sales): require application use cases and repository ports`
  - Ports: `InventoryRepository`, `OrderRepository`, `IdempotencyStore`.
  - Use cases: `InitializeInventory`, `GetAvailableSeats`, `PurchaseTickets`, `GetOrder`.
  - Unit tests using in-memory fake adapters.
- [ ] 2.2 `feat(sales): implement application use cases and ports`
  - Application logic in `services/sales/src/sales/application/`.

## 3. Database Persistence, Alembic and Concurrency (TDD)

- [ ] 3.1 `feat(sales): initialize Alembic and create database schema migrations`
  - Configure `alembic/` in `services/sales/`.
  - Migration script for `seats`, `orders`, `tickets`, and `idempotency_keys` tables.
- [ ] 3.2 `test(sales): require SQLAlchemy repositories with atomic locking and idempotency persistence`
  - Test `SELECT ... FOR UPDATE` concurrency protection and duplicate key prevention against PostgreSQL in Docker.
- [ ] 3.3 `feat(sales): implement SQLAlchemy repository adapters`
  - Concrete adapters in `services/sales/src/sales/infrastructure/`.

## 4. API Endpoints, Idempotency Middleware and Claims (TDD)

- [ ] 4.1 `test(sales): require REST endpoints for inventory and idempotent purchases`
  - Test `POST /events/{event_id}/inventory` (Admin).
  - Test `GET /events/{event_id}/seats` (Available seats).
  - Test `POST /events/{event_id}/orders` with `Idempotency-Key` (Client purchase, duplicate replay, mismatch error).
  - Test `GET /orders/{order_id}`.
- [ ] 4.2 `feat(sales): implement REST controllers and Pydantic schemas`
  - Routers in `services/sales/src/sales/api/`.
  - Token claims decoding helper (`sub` as customer_id, role validation).

## 5. ADRs, Bruno API Collection and Documentation

- [ ] 5.1 `docs(sales): add ADR-0008 (Payment in Stage II - D-25)`
  - `docs/adr/adr-0008-pago-en-la-etapa-ii.md`
- [ ] 5.2 `docs(sales): add ADR-0009 (Concurrency and Idempotency on PostgreSQL - D-30)`
  - `docs/adr/adr-0009-concurrencia-e-idempotencia-postgresql.md`
- [ ] 5.3 `docs(sales): add ADR-0010 (API and Contract Testing with Bruno - D-24)`
  - `docs/adr/adr-0010-tests-de-api-y-contrato.md`
- [ ] 5.4 `test(sales): add Bruno API test collection`
  - Automated collection in `tests/api/sales/`.
- [ ] 5.5 `docs(sales): update AGENTS.md with reference hexagonal service conventions (D-33)`
- [ ] 5.6 `docs(sales): record weekly log and update plan status`
