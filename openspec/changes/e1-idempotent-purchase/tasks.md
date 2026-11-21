# Tasks

Implementation tasks for `e1-idempotent-purchase` (PLAN 7.3, Core Domain).

Follows strict TDD: commit a failing `test(...)` before the `feat(...)` or `fix(...)` that makes it pass (RB-12).
All lint, type checks, and tests run inside Docker containers (D-12).

## 1. Domain Model, Hexagonal Enforcement and Invariants (TDD)

- [x] 1.1 `feat(sales): configure import-linter contract for hexagonal architecture (D-33)`
  - Configure `import-linter` rules in `services/sales/` and CI `quality` job to strictly enforce inward layer dependencies (`domain` isolated, `application` inward-only) guiding implementation from day 1.
- [x] 1.2 `test(sales): require domain entities and money value object`
  - Test `Seat`, `SeatStatus` (AVAILABLE, SOLD), `Order`, `OrderStatus` (CONFIRMED), `Ticket`, `Money` (ARS centavos).
  - Invariants: cannot sell unavailable seat, non-empty and unique seat IDs in purchase (`uniqueItems: true`), non-negative money.
- [x] 1.3 `feat(sales): implement domain entities and value objects`
  - Pure Python in `services/sales/src/sales/domain/` with zero external dependencies.

## 2. Application Layer, Ports and Use Cases (TDD)

- [x] 2.1 `test(sales): require application use cases and repository ports`
  - Ports: `InventoryRepository`, `OrderRepository`, `IdempotencyStore`.
  - Use cases: `InitializeInventory`, `GetAvailableSeats`, `PurchaseTickets`, `GetOrder` (with customer authorization).
  - Unit tests using in-memory fake adapters, including BOLA authorization checks.
- [x] 2.2 `feat(sales): implement application use cases and ports`
  - Application logic in `services/sales/src/sales/application/`.

## 3. Database Persistence, Alembic and Concurrency (TDD)

- [x] 3.1 `test(sales): require Alembic migrations and database schema`
  - Test migration scripts create tables: `seats`, `orders`, `tickets` with `UNIQUE(event_id, seat_id)`, and `idempotency_keys` with `PRIMARY KEY (customer_id, key)` and nullable `response_status` / `response_body`.
  - Verify container startup automatically runs migrations (`alembic upgrade head`).
- [x] 3.2 `feat(sales): initialize Alembic and create database schema migrations`
  - Configure `alembic/` in `services/sales/` and update compose entry.
- [x] 3.3 `test(sales): require SQLAlchemy repositories with ordered row locking and idempotency persistence`
  - Test `SELECT ... FOR UPDATE ORDER BY seat_id` deadlock prevention and concurrency protection in Docker.
  - Test key-reservation-first idempotency: sequential retry replay scenario and simultaneous concurrent double-click scenario.
  - Test rollback behavior: failure in order creation leaves no persisted idempotency key.
- [x] 3.4 `feat(sales): implement SQLAlchemy repository adapters`
  - Concrete adapters in `services/sales/src/sales/infrastructure/`.

## 4. Contract Test and Bruno API Collection (D-24)

- [x] 4.1 `test(sales): require contract test between openapi.yaml and FastAPI schema`
  - CI check `contract-test` comparing committed `services/sales/openapi.yaml` against dynamic FastAPI OpenAPI.
- [x] 4.2 `test(sales): add Bruno API test collection`
  - Automated collection in `tests/api/sales/` covering inventory, seat query, purchase, idempotency replay, and error scenarios against the Gateway.
- [x] 4.3 `test(sales): add system isolation test when catalog is unavailable`
  - Smoke-test scenario verifying `sales` serves requests through the Gateway when `catalog` is stopped.

## 5. API Endpoints, Idempotency Middleware and Claims (TDD)

- [x] 5.1 `test(sales): require REST endpoints for inventory and idempotent purchases`
  - Test `POST /events/{event_id}/inventory` (Admin role, 401 unauthenticated, 403 forbidden).
  - Test `GET /events/{event_id}/seats` (Requires authentication, 401 unauthenticated, 403 forbidden).
  - Test `POST /events/{event_id}/orders` with `Idempotency-Key` (Client purchase, duplicate replay, 400 on missing key, 422 payload mismatch, 422 empty/duplicate seats).
  - Test `GET /orders/{order_id}` with BOLA protection (404 on other customer's order).
- [x] 5.2 `feat(sales): implement REST controllers, Pydantic schemas, and token claims`
  - Routers in `services/sales/src/sales/api/`.
  - Custom FastAPI exception handler for missing/invalid `Idempotency-Key` header returning `400 Bad Request` (overriding default 422).
  - Token claims decoding helper (`sub` as customer_id, role validation).
  - Environment variable `SALES_AUTH_REQUIRED` handling.

## 6. Frontend Purchase Screen (React + shadcn/ui)

- [x] 6.1 `docs(sales): add UI mockups for seat selection and order confirmation`
  - Store mockups in `docs/mockups/sales/` depicting seat selection grid, cart summary, and confirmed order view.
- [ ] 6.2 `test(frontend): require seat selector grid, cart summary, and purchase flow` (Deferred: team agreed to implement full React purchase screens in a dedicated Stage I change after Nov 25 bootstrap baseline)
  - Vitest + React Testing Library tests for `/events/:eventId/buy` and `/orders/:orderId`.
  - Test seat selection, price calculation in ARS, idempotency key generation, and purchase submission.
- [ ] 6.3 `feat(frontend): implement seat selection grid and order confirmation views` (Deferred: team agreed to implement full React purchase screens in a dedicated Stage I change after Nov 25 bootstrap baseline)
  - React components with Tailwind CSS and shadcn/ui.
  - Routing and API integration with `/api/sales`.

## 7. Architecture Enforcement, ADRs and Documentation

- [x] 7.1 `docs(sales): add ADR for Payment in Stage II (D-25)`
  - Number assigned upon merge into `main` (ADR-0007).
- [x] 7.2 `docs(sales): add ADR for Concurrency and Idempotency on PostgreSQL (D-30)`
  - Number assigned upon merge into `main` (ADR-0008).
- [x] 7.3 `docs(sales): add ADR for API and Contract Testing with Bruno (D-24)`
  - Number assigned upon merge into `main` (ADR-0009).
- [x] 7.4 `docs(sales): update AGENTS.md with reference hexagonal service conventions (D-33)`
- [x] 7.5 `docs(sales): update CONTRIBUTE.md with sales test commands and seed data`
- [x] 7.6 `feat(ci): add contract-test to required GitHub branch ruleset checks (PLAN 6.4)`
- [x] 7.7 `docs(sales): record weekly log and update plan status`
