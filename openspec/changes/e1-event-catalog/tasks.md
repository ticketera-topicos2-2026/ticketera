# Tasks

> **Priority:**
> - `P1` = in the delivery of 2026-11-25 (APIs, tests and mockups, E-03 in PLAN 2.4). `P2` = after it, still
>   required to close Stage I (D-28).
> - Groups 1 to 7 are P1 only if the skeleton of `e1-idempotent-purchase` (#32) is merged by 2026-11-22; otherwise
>   they move to P2, to be confirmed by the team. Group 8 (screens) is P2.
>
> **Dependencies:**
> - 1 → 2 → 3 → 4 → 6. Group 1 starts once the skeleton of #32 (four layers, `import-linter`, Alembic
>   conventions and the `contract-test` check) is merged.
> - Group 5 starts once the access check of `e1-identity-access` (#30, group 1) is merged.
> - Group 7 can start at once. Group 8 needs the GoPass base and the sign-in of #30, group 2.
>
> **Pull requests:**
> - Planning: this change, with `Refs #35`.
> - Implementation: groups 1 to 4 (backend), 5 and 6 (gateway and API tests), 7 (mockups) and 8 (screens), each
>   with `Refs #35`; the last one merged carries `Closes #35` (D-37).
> - Reviewer: C (PLAN 6.1). A also reviews group 5.
>
> **Commits:** each red test task is committed as `test(...)` before the `feat(...)` that makes it pass (RB-12).
>
> **Notation:**
> - `Req` = requirement of the spec named after it: `specs/catalog/<capability>` or `specs/platform/api-gateway`.
> - `EC` = decision in `design.md`.
> - Tests live in `services/catalog/tests/{unit,integration,acceptance}/`, each with a docstring naming its
>   requirement and scenario (PLAN 3.4).

## 1. Domain model (B) [P1]

- [x] 1.1 Write `tests/unit/test_event.py` (red): creating a draft (owner, version 1, `DRAFT`); every validation
  rule of the event and its zones; seat ids of a numbered zone; replacing a draft with the current and a stale
  version; refusing to replace a published event; publishing with and without zones, with a past start, and
  twice (Req event-management: Event data is validated - all scenarios; Each zone has a ticket modality - all
  scenarios; A draft is edited with its current version - Scenarios: Edit with the current version, Edit with a
  stale version, Edit of a published event; A draft is published once it is complete - Scenarios: Complete draft
  published, Draft without zones, Draft that starts in the past, Publishing twice; EC-01, EC-07). Verify: the
  tests fail because the module is missing.
- [x] 1.2 Implement `domain/event.py` and its value objects, pure Python, raising domain errors; `publish` raises
  `EventPublished` (EC-01, EC-07, EC-13). Verify: the tests of 1.1 pass; `import-linter` passes; coverage of
  `domain` of 80 % or more (D-18).

## 2. Application layer (B) [P1]

- [x] 2.1 Write `tests/unit/test_event_use_cases.py` (red) with in-memory fakes of `EventRepository`,
  `IdempotencyStore` and a fixed clock: `CreateEvent`, `ReplaceEvent`, `PublishEvent`, `GetManagedEvent`,
  `ListManagedEvents`, `ListPublishedEvents`, `GetPublishedEvent`, given the user's `sub` and roles as a value.
  Cover a `CLIENT` refused; an `EVENT_OWNER` acting on another owner's event getting "not found"; an `ADMIN` acting
  on any event without changing its owner; listing scoped by owner; the public list hiding drafts and past events
  (Req event-management: An EVENT_OWNER or an ADMIN creates a draft event - all scenarios; An EVENT_OWNER manages
  only their own events - all scenarios; Managers list the events they can manage - Scenarios: EVENT_OWNER lists
  their events, ADMIN lists every event; Req event-browsing: The public catalog lists only published events -
  Scenarios: Visitor without a token, Draft not listed; EC-04). Verify: the tests fail.
- [x] 2.2 Implement the use cases and ports in `application/` (EC-04, EC-05, EC-06). Verify: the tests of 2.1
  pass; coverage of `application` of 80 % or more.

## 3. Persistence, idempotency and concurrency (B) [P1]

- [x] 3.1 Write `tests/integration/test_migrations.py` (red): `alembic upgrade head` on an empty `catalog`
  database creates the four tables, the checks and the indexes of EC-08; `downgrade base` removes them. Verify: the
  tests fail.
- [x] 3.2 Initialize Alembic in `services/catalog/` and write the migration; the container runs `alembic upgrade
  head` before Uvicorn starts (D-33). Verify: the tests of 3.1 pass; `docker compose down -v` and `up` leave
  `catalog` healthy.
- [x] 3.3 Write `tests/integration/test_event_repository.py` (red): save and load an event with its zones and
  participants; the conditional update by version and state; the public query with filters, order and
  pagination; the idempotent create, including 10 concurrent requests with the same key, the same key with a
  different body, and two users with the same key; two concurrent edits of the same version; publishing while an
  edit runs (Req event-management: Event creation is idempotent - all scenarios; A draft is edited with its
  current version - Scenario: Two concurrent edits of the same version; A draft is published once it is complete -
  Scenario: Publish and edit at the same time; Req event-browsing: The public catalog is filtered and paginated -
  Scenarios: Filter by type and date range, Second page; EC-05, EC-06). Verify: the tests fail.
- [x] 3.4 Implement the SQLAlchemy repository and idempotency store in `infrastructure/` with the transactions of
  the design. Verify: the tests of 3.3 pass against PostgreSQL in Docker.

## 4. API (B) [P1]

- [x] 4.1 Write `services/catalog/openapi.yaml` with the paths and schemas of the design, and the contract test
  (red) in the check of D-24 (EC-02, EC-10, EC-11). Verify: the contract test fails because the endpoints are
  missing.
- [x] 4.2 Write `tests/acceptance/test_service_access.py` (red) for the token-claims contract on the management
  API, with test tokens (Req service-access: every requirement, all scenarios). Verify: the tests fail.
- [x] 4.3 Implement the authentication adapter in `api/`: decode the payload, take `sub` and the platform roles
  from `realm_access.roles`, `401` for no or an undecodable token or a token only in the query string, and store
  the accepted `sub` in `request.state.user_id` (RL-06 of `e1-request-log`). Verify: the tests of 4.2 pass.
- [x] 4.4 Write `tests/acceptance/test_manage_events_api.py` and `test_public_events_api.py` (red):
  - status codes and the `422` field names of every management scenario; `400` without `Idempotency-Key`;
  - `404` across owners; `limit` above 100;
  - public list and detail without and with valid, tampered and expired tokens; drafts and owners never shown;
    `405` for `POST /events`; `422` for an invalid filter
  (Req event-management: every requirement, the scenarios that need the API; Req event-browsing: every requirement
  except "The public catalog answers quickly"). Verify: the tests fail.
- [x] 4.5 Implement the routers, the `400` handler for the missing key, and the request and response schemas with
  `extra="forbid"` (EC-02, EC-09, EC-10, EC-12). Verify: the tests of 4.4 pass; the contract test passes; `ruff`,
  `mypy` and `import-linter` pass in the container.

> **Groups 1 to 4, done on 2026-11-21.** 132 tests pass in the container (unit, integration against PostgreSQL,
> acceptance and contract); the smoke test and the database isolation test pass; an end-to-end flow through the
> gateway creates, retries, publishes and reads an event. Notes:
> - The idempotency table stores the event id, and a replay returns that event (design, Persistence).
> - `catalog` starts with `bin/run` (migrations, then Uvicorn) and its healthcheck got a `start_period` of 60 s,
>   because the migrations made a cold start exceed the default 45 s on a loaded machine.
> - The contract test also compares operation ids, success statuses and request body schemas.
> - Coverage of `domain` and `application` (D-18) is not measured yet: the services have no `pytest-cov`.

## 5. Gateway public paths (B; reviewed by A) [P1]

- [x] 5.1 Write the smoke checks (red) in `tests/smoke/identity-checks.sh`: `GET` and `HEAD` on the public catalog
  paths without a token reach `catalog`; `GET /api/catalog/manage/events`, `POST /api/catalog/events`,
  `/api/catalog/events/`, `/events/<uuid>/zones`, `/events/not-a-uuid` and `GET /api/sales/events` without a token
  answer `401` (Req api-gateway: Public paths skip the access check - the scenarios added by this change). Verify:
  the checks fail.
- [ ] 5.2 Extend the public-path map of the gateway template with the strict catalog pattern
  `^(GET|HEAD):/api/catalog/events(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})?(\?.*)?$` (EC-03).
  Verify: the checks of 5.1 and every existing smoke check pass.

## 6. API tests (B) [P1]

- [x] 6.1 Write `tests/api/catalog/` in Bruno with the test users of #30: create with a key and retry it; edit;
  stale version; publish; public list and detail; `403` for a `CLIENT`; `404` across owners (Req event-management
  and event-browsing, the main scenarios). Verify: the collection passes with the runner of D-24. Done: 13 requests
  and 20 assertions pass. The runner of D-24 did not exist, so this change adds a minimal one, `tests/api/run.sh`:
  Bruno CLI 4.3.0 from a lockfile in the pinned Node container of the CI, in the gateway's network namespace. Until
  the test users of #30 exist it passes unsigned test tokens with a new `sub` per run; once the access check of #30
  is merged it must get real tokens from `ticketera-api-tests`.
- [x] 6.2 Write `tests/smoke/measure-catalog-latency.sh`: creates and publishes 100 events through the gateway,
  then measures 10 warm-up and 100 requests of `GET /api/catalog/events?limit=100` and prints the p95 (Req
  event-browsing: The public catalog answers quickly). Verify: the p95 is 300 ms or less on a member's machine;
  the result goes to the team log. Done: p50 26 ms, p95 58 ms on 2026-11-21 (6 GiB machine, WSL 2); to the team
  log with task 9.2.

## 7. Mockups (B) [P1]

- [x] 7.1 Draw the mockups of the public catalog, the event detail, "My events", the event form (with zones of
  both modalities and participants) and the publish errors, with the GoPass palette and fonts (D-38), in
  `docs/mockups/catalog/` as PNG exports with their source; sample data only. Verify: reviewed by C in the pull
  request. Done: HTML sources in `docs/mockups/catalog/src/` with a shared `gopass.css`, rendered with a headless
  browser; `docs/mockups/catalog/README.md` maps each screen to its route and specs. The `409` of a stale version
  is shown on the publish-errors screen.

## 8. Screens (B) [P2]

- [ ] 8.1 Write the Vitest and React Testing Library tests (red) of the five screens against a mocked API: filters
  and pagination; the detail with both modalities; "My events" hidden from a `CLIENT`; the form validation, the
  `409` message and the publish errors (EC-14). Verify: the tests fail.
- [ ] 8.2 Implement the routes and screens on the GoPass base and the `AuthProvider` of #30 (EC-14). Verify: the
  tests of 8.1 pass; ESLint and `tsc --noEmit` pass; the flow works by hand in a browser, recorded with screenshots
  in the team log.

## 9. Documentation and team log (B)

- [x] 9.1 Update `CONTRIBUTE.md` (Spanish): how an `ADMIN` loads the `sales` inventory of a published event using
  the catalog's seat ids (`<zone code>-<n>` as `seat_id`, the zone code as `category`). Verify: reviewed in the
  pull request. Done: section «Catálogo de eventos e inventario de `sales`», checked end to end on 2026-11-21
  (catalog event published, its seat ids loaded by an ADMIN, `sales` lists them as AVAILABLE); unnumbered zones
  are not loadable yet, because `sales` sells numbered seats only in Stage I.
- [x] 9.2 Write the team log entry `docs/bitacora/<date>-e1-event-catalog.md`: what was built, the latency
  measured, the mockups and screenshots, the open points (S-03, Event Storming) and who completed each part.
  Verify: the entry exists. Done: `docs/bitacora/2026-11-21-e1-event-catalog.md`; the screenshots of the screens
  come with group 8.
