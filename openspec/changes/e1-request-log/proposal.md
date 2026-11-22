# Proposal

> Builds on the token-claims contract and the gateway log rule of `e1-identity-access` (#30, merged) and on the
> four-layer service skeleton of `e1-idempotent-purchase` (D-33, #32). The middleware for `sales` lands after the
> implementation of #32 merges (see `tasks.md`).

## Why

Nobody can tell today which requests reach the system, who made them, how they ended or how long they took:
each service writes only the default Uvicorn access line, and nothing ties a request at the gateway to the
same request inside a service. DT-03 requires an HTTP request log with timing in every service from Stage I,
and D-23 fixes its shape: one JSON line per request to stdout, a correlation id that only the gateway
generates, and Loki with Grafana to collect and query the lines (PLAN 4.6). Stage II and III (caching, queues,
stress test) need this log to measure their effect, so it must exist before them.

## What Changes

- **Correlation id at the gateway:** NGINX generates a correlation id for every request, always overwriting
  any value sent by the client, forwards it to the service in a request header and returns it in the response
  (D-23).
- **Gateway access log:** the gateway writes its own JSON line per request, including the requests it rejects
  before they reach a service (authentication failures at the perimeter, unknown routes, 502 from a stopped
  service).
- **Request-log middleware in every backend service** (`catalog`, `sales`, `payments`), in the order of
  PLAN 4.6: start a timer on arrival, process authentication, run the endpoint, record method, route, user,
  status code, duration and correlation id, and return the response. Rejected authentications are logged too.
  The user is the `sub` claim of the token; anonymous requests log no user.
- **Log line contract:** one JSON object per line on stdout, field names in English, the same schema in every
  service and in the gateway. Tokens, `Authorization` and `Cookie` headers, request and response bodies, and
  payment data are never logged.
- **One implementation per service, one contract for all:** the middleware lives in the `api` layer of each
  service, following the reference skeleton of D-33; each service keeps its own small copy (design RL-04), and a
  JSON Schema shared by the tests checks that every service and the gateway write the same line.
- **Collection and query:** new containers in Compose: Alloy (collector reading the Docker logs), Loki
  (storage) and Grafana (query), with images pinned by digest, healthchecks, Grafana published only on
  `127.0.0.1` and its credentials taken from `.env` (placeholders in `.env.example`); a provisioned Loki data
  source and a starter dashboard (requests per service, status codes, duration percentiles).
- **ADR of D-23** in `docs/adr/` with the `create-architectural-decision-record` skill (D-27): log format,
  correlation id, collection stack, retention and excluded fields.
- **Tests:** unit and API tests of the middleware per service (field set, duration, status, user, correlation
  id, excluded fields, logged authentication failures); a Bruno check through the gateway that the response
  carries a correlation id and that a client-supplied one is replaced (D-24); the smoke test also checks that
  Loki and Grafana are healthy.

## Capabilities

### New Capabilities

- `platform/request-log`: the per-request JSON log line, its fields, excluded data and ordering in every
  backend service.
- `platform/request-correlation`: generation and propagation of the correlation id by the gateway.
- `platform/log-collection`: Alloy, Loki and Grafana in the local environment, their access and retention.

### Modified Capabilities

- `platform/api-gateway`: the gateway generates the correlation id and writes a JSON access log.
- `platform/local-environment`: new containers with healthchecks; Grafana is the third published port.

## Non-goals

- Distributed tracing or metrics with OpenTelemetry (rejected alternative in D-23).
- Storing the log in PostgreSQL or writing it from each handler (rejected alternative in D-23).
- Alerting, production retention or log shipping outside the local machine.
- Business audit events (who bought which ticket); this change logs HTTP requests only.
- The frontend: browser requests are logged where they enter, at the gateway.

## Impact

- **Bounded contexts:** none of the domain models change. Affects the platform (gateway, Compose, CI) and the
  `api`/`infrastructure` layers of `catalog`, `sales` and `payments`.
- **Responsible:** Integrante B (PLAN 7.3). Review of the gateway and Compose parts by Integrante A, who owns
  the platform (PLAN 6.1).
- **Coordination:** `e1-identity-access` (A) defines how the gateway validates tokens and what it forwards;
  the user field depends on that contract. `e1-idempotent-purchase` (C) is changing `sales` at the same time,
  so the middleware for `sales` lands after its skeleton is merged.
- **Resources:** three more containers; the onboarding of group 8 showed start-up problems on machines with
  about 3 GiB for WSL (#24), so the design sets memory limits for Loki, Alloy and Grafana, and no application
  container depends on them, so a member can stop them without affecting the system (RL-11).
- **Not applicable:** this change adds no FastAPI endpoint, so it has no OpenAPI contract test, and no screen, so
  it has no mockups; the Grafana dashboard is provisioned as a file.

## Risks and Rollback

- **Sensitive data in the log** (tokens, personal data): mitigated by an allow-list of fields instead of a
  deny-list, and by tests that fail if `Authorization` or a body appears in a line.
- **Spoofed correlation id:** the gateway always overwrites it; a Bruno test proves it.
- **Slower start-up and more memory** on small machines: limits and healthcheck `start_period` in the design;
  the observability containers do not block the health of the application services.
- **Log volume:** Loki retention is bounded and defined in the ADR.
- **Rollback:** revert the pull request; services return to the default Uvicorn access log, and removing the
  three containers does not touch any service database.
