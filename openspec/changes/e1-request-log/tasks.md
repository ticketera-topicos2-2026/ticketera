# Tasks

> **Priority:** `P1` = in the delivery of 2026-11-25. `P2` = after it, still required to close Stage I (D-23,
> DT-03). Groups 1 and 2 are P1; group 4 is P1 if group 1 is merged by 2026-11-23, otherwise P2, to be confirmed
> by the team.
> **Dependencies:** 1 → 2 → 4. Group 3 starts when the implementation of `e1-idempotent-purchase` (#32) that adds
> the `sales` authentication adapter is merged. Group 1 rebases on the gateway work of `e1-identity-access` (#30)
> if that merges first (design, "Rebase with #30"). Group 5 needs the Bruno runner of D-24. Group 6 closes the
> change.
> **Pull requests:** one branch and one pull request per group, each with `Refs #34`; the one merged last also
> carries `Closes #34` (D-37). Reviewer: C (PLAN 6.1); A also reviews groups 1 and 4, which touch the gateway and
> Compose (CODEOWNERS).
> **Commits:** each red test task is committed as `test(...)` before the `feat(...)` that makes it pass (RB-12).
> Notation: `Req` = requirement of the spec named after it (`specs/platform/<capability>`); `RL` = decision in
> `design.md`. This change adds no FastAPI endpoint and no screen, so it has no OpenAPI contract test and no
> mockups (proposal, Impact).

## 1. Gateway: correlation id and JSON access log (B, feature/e1-request-log-gateway) [P1]

- [x] 1.1 Write `tests/platform/gateway-log.schema.json` (fields, types, `additionalProperties: false`) and
  `tests/platform/request-log.schema.json` (same for service lines), with `unittest` tests that a valid example
  passes and examples with an extra field, a missing field, a string status or a 31-character correlation id fail;
  the lines are checked by `scripts/check_log_lines.py`, standard library only like the other platform checks,
  which supports the subset of JSON Schema the two schemas use and rejects any other keyword
  (Req api-gateway: The gateway access log line has a fixed set of fields; Req request-log: The request log line
  has a fixed set of fields). Verify: `python -I -B -m unittest discover -s tests/platform` runs the new tests.
- [x] 1.2 Create `tests/smoke/request-log-checks.sh`, sourced by `smoke-test.sh`, and write the gateway checks
  (red): `X-Correlation-ID` of 32 hex on `200`, `401`, `404` and `502` answers; different ids on two requests and
  on 50 concurrent ones; a forged header replaced; one gateway line per request valid against
  `gateway-log.schema.json` for `200`, `401`, `404`, `421` and `502`; no line for `/healthz`; a path with `%22`
  and `%0A` gives one valid line; a query-string token in no line (Req request-correlation: The gateway gives
  every request a correlation id - all scenarios; The correlation id is never taken from the client - both
  scenarios; Req api-gateway: both requirements, all scenarios). The `502` comes from the test-only route
  `tests/smoke/gateway/unavailable.conf` to a closed port of the echo service, because stopping a real service
  would change its address (DS-07); the `401` checks are skipped until the access check of #30 is merged. Verify:
  the checks fail on the current gateway.
- [x] 1.3 In `infra/gateway/templates/default.conf.template`: `log_format ticketera_json escape=json` with the
  fields of the spec, `access_log /var/log/nginx/access.log ticketera_json` (the image links it to standard
  output) in both servers, `add_header X-Correlation-ID
  $request_id always` at server level, and the IA-08 rule kept in the comment; in
  `snippets/forwarded-headers.conf`, `proxy_set_header X-Correlation-ID $request_id` (RL-01, RL-02, RL-09).
  Verify: the checks of 1.2 pass; the smoke test passes.
- [x] 1.4 Check that the identity service receives the correlation id: through the existing echo route of the
  smoke test, which includes the same forwarding snippet as every route, `/auth/` included, the received header
  equals the response header (Req
  request-correlation: The gateway forwards the correlation id to the service - both scenarios). Verify: the check
  passes in the smoke test.

## 2. Request log middleware in catalog and payments (B, feature/e1-request-log-services) [P1]

- [x] 2.1 Write `services/catalog/tests/unit/test_request_log.py` (red) against a minimal Starlette app wrapped by
  `RequestLogMiddleware` with an in-memory writer: exact field set and types; `route` template and `null` on
  `404`; status `500` and the exception re-raised; `401` with `null` user and `403` with the `sub` stored in
  `request.state.user_id`; `X-User-Id` ignored; `422` logged; a 200 ms endpoint gives `0.2 <= duration < 0.4`;
  malformed and missing correlation ids give `null`; a failing writer leaves the response unchanged; 50
  concurrent requests give 50 lines with their own ids and users (Req request-log: every requirement except "The
  server writes no other access log"; Req request-correlation: Services accept only a well-formed correlation id
  - both scenarios; RL-03, RL-05, RL-06, RL-07). Verify: the tests fail (module missing) with
  `docker compose run --rm catalog pytest`.
- [x] 2.2 Implement `services/catalog/src/catalog/api/request_log.py` (RL-04, RL-05, RL-08, RL-10). Verify: the
  tests of 2.1 pass; `ruff check .` and `mypy` pass in the container.
- [x] 2.3 Write `services/catalog/tests/acceptance/test_request_log_api.py` (red), then add the middleware in
  `api/app.py`: the real app through `TestClient` writes one line per request to stdout with exactly the fixed
  fields; a request with a bearer token, a `Cookie` header, `?access_token=...` and a JSON body with a name and an
  email writes none of those values (Req request-log: The request log never contains sensitive data - all
  scenarios). The shared schema lives outside the service's build context and mount, so the smoke test of 2.4
  checks the real lines against it (Scenario: Same schema in every service). Verify: the tests fail before the
  middleware is added to the app, pass after.
- [x] 2.4 Add `--no-access-log` to the `catalog` command in `docker-compose.yml` and to the image's `CMD`; add the
  smoke checks (red first): no Uvicorn access line in `docker compose logs catalog`; the `catalog` line of a
  request through the gateway is valid against `tests/platform/request-log.schema.json` and has the same
  correlation id as the gateway line; `check_cors` follows the preflight and the GET by their correlation ids
  instead of query-string markers, which the request log no longer shows (Req request-log: The server writes no
  other access log; The request log line has a fixed set of fields - Scenario: Same schema in every service; Req
  request-correlation: The same correlation id ties the gateway line to the service line). Verify: the smoke test
  passes.
- [x] 2.5 Repeat 2.1 to 2.4 for `payments` (copy of the module, `service_name="payments"`, same tests). Verify: the
  same tests pass in `payments`; the smoke test passes.

## 3. Request log middleware in sales (B, feature/e1-request-log-sales) [P1, after #32's implementation]

- [x] 3.1 Repeat 2.1 to 2.4 for `sales`, plus an acceptance test that an authenticated `CLIENT` request logs its
  `sub` and a `CLIENT` call to an `ADMIN` endpoint logs `403` with that `sub` (Req request-log: The logged user is
  the token's sub - all scenarios; Every backend service writes one log line per request - Scenario: Request
  rejected by the service's access rules). Verify: the tests pass in `sales`; the smoke test passes.
- [x] 3.2 If the `sales` authentication adapter does not yet store the accepted `sub` in
  `request.state.user_id`, add that line in a separate `feat(sales)` commit, agreed with C, after the red test of
  3.1 (RL-06). Verify: the test of 3.1 for `user_id` passes.

## 4. Log collection: Alloy, Loki and Grafana (B, feature/e1-request-log-collection)

- [x] 4.1 Write the smoke checks (red), in `tests/smoke/log-collection-checks.sh`: `loki`, `alloy` and `grafana` healthy; a Loki query for a correlation id
  returns the gateway line and the service line within 15 s; a query on `service="sales"` returns only `sales`
  lines; Grafana answers `401` to `/api/search` without credentials and lists the Loki data source and the
  request log dashboard with the `.env` credentials; Grafana published only on `127.0.0.1` and Loki not
  published; each of the three has a memory limit, summing to 768 MiB or less; with the three stopped, every
  gateway route answers as before (Req log-collection: every requirement except "Log retention is bounded" -
  Scenario: Clean reset; Req local-environment: both requirements, all scenarios). Loki is queried through
  Grafana's data source proxy, because it publishes no port. The non-root check allows root only for `alloy`
  (RL-12; Req log-collection: The log collector has read-only access to the container runtime - Scenario:
  Collector runs as root without capabilities). Verify: the checks fail.
- [x] 4.2 Add `infra/observability/loki/config.yaml` with 7-day retention (RL-14) and a `unittest` in
  `tests/platform/` that reads it and asserts `retention_enabled` and `retention_period: 168h` (Req
  log-collection: Log retention is bounded - Scenario: Retention setting). Verify: the test passes.
- [x] 4.3 Add `infra/observability/alloy/config.alloy` (RL-12, RL-13) and the Grafana provisioning: Loki data
  source and `dashboards/request-log.json` with requests per service, per status class and p50/p95/p99 of
  `duration_seconds`, and a logs panel filtered by a correlation id (Req log-collection: Grafana opens with the
  request log ready to use). Verify: the dashboard loads by hand with traffic; recorded in the team log. Done on
  2026-11-21: with traffic through the gateway, every panel query of the dashboard, run through Grafana's API,
  returned data (3 services, 2 status classes, p50/p95/p99 per service, and the 2 lines of a chosen correlation
  id); recorded in the team log. Screenshot taken on 2026-11-22 with every panel showing data:
  `docs/bitacora/evidencia/e1-request-log/dashboard-request-log.png`.
- [x] 4.4 Add `loki` (image of RL-17), `alloy` and `grafana` to `docker-compose.yml`: images pinned by index
  digest, healthchecks with tools each image has (DS-12), `mem_limit`, `cap_drop: ALL`, `no-new-privileges`, the
  `observability` network, the read-only Docker socket for Alloy as root (RL-12), the volumes
  `ticketera-loki-data` and `ticketera-alloy-data`, Grafana on
  `127.0.0.1:${GRAFANA_PORT}` with `GRAFANA_ADMIN_USER` and `GRAFANA_ADMIN_PASSWORD` as `${VAR:?}`; add the three
  variables with placeholders to `.env.example`; no application container gets a `depends_on` on them
  (RL-11, RL-15, RL-16). Verify: the checks of 4.1 pass; `docker compose config` without
  `GRAFANA_ADMIN_PASSWORD` fails and names it (Req log-collection: Grafana requires the credentials from local
  configuration - Scenario: Missing password); `down -v` and `up` leave Loki empty (Scenario: Clean reset).
  Done: the checks pass locally and in CI, and the missing password stops Compose naming it. Clean reset checked
  on 2026-11-21: a correlation id found in Loki before `down -v` is gone after `up`, the Loki volume is new, and
  lines written after the reset are collected. On a machine with 6 GiB of RAM the cold start after `down -v`
  (realm import, Grafana migrations) did not reach healthy in 15 minutes, and Alloy can lose its Docker API
  connection under that load until it is restarted; both are documented in `CONTRIBUTE.md`.
- [x] 4.5 Measure the smoke-test duration and the memory of the three containers in CI and on a member's machine;
  record both in the team log; the CI still finishes within 15 minutes (Req continuous-integration of
  `project-bootstrap`: The CI finishes within 15 minutes). Verify: numbers recorded. Recorded in the team log of
  2026-11-20: smoke-test job 2 min 43 s (1 min 53 s before); Loki ~100 MiB, Alloy ~90 MiB, Grafana ~210 MiB.

## 5. API tests (B, with group 4 or later) [P2]

- [x] 5.1 Write `tests/api/platform/` in Bruno: the response carries `X-Correlation-ID`, and a forged one is
  replaced (Req request-correlation: The gateway gives every request a correlation id - Scenario: Forwarded
  request; The correlation id is never taken from the client - Scenario: Client sends its own correlation id).
  Verify: the collection passes with the runner of D-24.

## 6. ADR, documentation and team log (B, in the pull request of group 4)

- [x] 6.1 Write the ADR of D-23 in `docs/adr/` with the `create-architectural-decision-record` skill: log line
  format and excluded fields, correlation id, Alloy + Loki + Grafana, read-only Docker socket as an accepted risk
  with a socket proxy as the upgrade path, 7-day retention; take its number when merging; update the link in
  `design.md` and the index in `docs/adr/README.md` (D-27, RL-01, RL-08, RL-11, RL-12, RL-14). Verify: the ADR
  is listed in the index and linked from the design. Done as ADR-0011 (`Proposed` until #39 is approved), with
  the template of the existing ADRs because the skill was not available; it also records the exception to DS-13
  and RL-17.
- [x] 6.2 Update `CONTRIBUTE.md` (Spanish): how to open Grafana, find a request by its correlation id, read the
  dashboard, and stop Loki, Alloy and Grafana on a machine with little memory; also what a new service does to
  write its line. Verify: a member follows it on a clean clone (pending, by the reviewer).
- [x] 6.3 Update `AGENTS.md`: a service never logs anything but the request log line's fields, and an
  authentication adapter stores the accepted `sub` in `request.state.user_id` (RL-06, RL-08). Verify: reviewed in
  the pull request.
- [x] 6.4 Write the team log entry `docs/bitacora/<date>-e1-request-log.md`: what was built, the measured memory
  and smoke-test time, the dashboard screenshot, and who completed each part. Verify: the entry exists (the
  README of the team log has a template, not an index). Done: `docs/bitacora/2026-11-20-e1-request-log.md`, with
  the dashboard screenshot of task 4.3 added on 2026-11-22.
