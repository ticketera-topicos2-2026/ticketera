# Proposal

## Why

The team cannot start Stage I features until it shares a contribution workflow and a system that already runs:
today the repository only holds the OpenSpec setup and `docs/PLAN.md`. This change establishes both, so every
later change (e1-*, e2-*, e3-*) is reviewed the same way and added on top of a walking skeleton that CI proves
works end to end (PLAN.md sections 6, 7.1 and 7.1.1).

## What Changes

- Contribution rules and conventions: `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTE.md`, pull request template,
  `CODEOWNERS`, `.gitignore`, `.editorconfig`, `.env.example`, MIT `LICENSE` (D-11); update of the existing
  `.gitattributes` (initial commit).
- Protection of `main` enforced through the GitHub ruleset, including the required status checks
  `openspec-validate`, `quality` and `smoke-test`.
- A single `docker compose up` from the repository root starts the whole system; every container has a
  healthcheck and waits for its dependencies to be healthy.
- Platform containers: one PostgreSQL container with one logical database and one role per service; the
  identity service (Keycloak) importing the `ticketera` realm with the roles `ADMIN`, `EVENT_OWNER` and
  `CLIENT`; an NGINX gateway that is the only entry point to the API and also routes to the identity service.
- Only the gateway and the frontend publish ports, on the local machine; the database and the identity service
  publish none.
- Backend skeletons for `catalog`, `sales` and `payments` with `GET /health` reporting service status and
  database connectivity, reachable through the gateway. `payments` is a Stage II context, so its skeleton has
  only `/health` (D-25).
- Frontend status page that shows the health of every service through the gateway (D-32).
- The ADR of D-29 (public routes `/api/<service>/` with no version), written in group 2 in `docs/adr/` (D-27).
- CI workflow on every pull request: `openspec validate --all --strict`, compose build, lint, type check,
  tests, and a smoke test of every health endpoint through the gateway.
- No secrets in the repository.

## Capabilities

### New Capabilities

- `platform/contribution-workflow`: branch and pull request rules for `main` (RB-01, RB-04, RB-05, RB-08):
  direct pushes rejected, one approval from another member, approvals dismissed on new commits, red required
  checks block the merge, AI usage declared in every pull request.
- `platform/local-environment`: single-command startup, healthchecks and ordered startup; only the gateway and
  the frontend publish ports, on the local machine, and the database and the identity service publish none;
  secrets kept out of the repository.
- `platform/api-gateway`: the gateway as the only API entry point; public routes `/api/<service>/...` to each
  backend service and `/auth/...` to the identity service, including its admin console; the identity
  service's health and metrics endpoints are never exposed through the gateway.
- `platform/database-isolation`: one logical database and one role per service, with no cross-service access.
- `platform/identity-provisioning`: the `ticketera` realm imported on startup with the roles `ADMIN`,
  `EVENT_OWNER` and `CLIENT`.
- `platform/service-health`: the `GET /health` contract of every backend service (status and database
  connectivity) and the frontend status page that displays it.
- `platform/continuous-integration`: the checks run on every pull request, their required names, and the
  smoke test covering the gateway, the `ticketera` realm, every backend health endpoint and the frontend.

### Modified Capabilities

None: the project has no specs yet.

## Non-Goals

- No business logic, domain model, business endpoints or database migrations.
- No authentication or role enforcement on endpoints; the `ticketera` realm only needs to contain the roles.
- No payment flow, payment endpoints or `PaymentProvider`: the payment gateway is Stage II, and the Stage I
  purchase has no payment step (D-25).
- No messaging, cache or Stage II/III containers (RabbitMQ, Redis, recommendation, search, sales-queue); Redis
  arrives in Stage II (D-30).
- No HTTP request log middleware, correlation id or log stack (Loki, Grafana, Alloy): change `e1-request-log`,
  Stage I (D-23, D-28).
- No API test collection (Bruno) or contract test: they arrive with the first e1-* change with endpoints (D-24).
- No reference skeleton (Alembic, import-linter): `e1-idempotent-purchase` sets it (D-33).
- No third-party skills for the assistants (D-26) and no Antigravity integration files: each arrives in its own
  pull request.
- No glossary, context map or Event Storming results; no ADR other than the one of D-29.
- No production deployment, TLS or published ports beyond the local machine.

## Bounded Contexts and Responsibility

Platform capabilities only; no bounded context is modeled. The `platform` folder under `specs/` stands in as the
context folder. The candidate contexts affected remain a hypothesis until the Event Storming: `identity`
(the identity service and the `ticketera` realm) and `catalog`, `sales` and `payments` (empty service
skeletons).

| Group | Scope | Owner | Branch |
| --- | --- | --- | --- |
| 1 | Conventions and rules files | A | `feature/bootstrap-conventions` |
| 2 | Platform: database, identity service, gateway, smoke test, CI workflow | A | `feature/bootstrap-platform` |
| 3 | `catalog` skeleton | B | `feature/bootstrap-catalog` |
| 4 | Frontend status page | B | `feature/bootstrap-frontend` |
| 5 | `sales` skeleton | C | `feature/bootstrap-sales` |
| 6 | `payments` skeleton (`/health` only, D-25) | C | `feature/bootstrap-payments` |
| 7 | Required status checks in the ruleset; runs right after group 2 is merged | A | none (settings only) |
| 8 | Onboarding on a clean clone (A coordinates; A, B and C each run it) | A | none |
| 9 | Verification and archive; commits the evidence of groups 7 and 8 | A | `feature/bootstrap-archive` |

Any fix found during onboarding gets its own branch and pull request.

## Prerequisites

Satisfied. The approval pull request (#4: `docs/PLAN.md` v0.4.0 and `openspec/config.yaml` 0.3.0) is merged
into `main`. Following the team meeting of 2026-10-27, it sets D-01 to D-34 to Approved and records the
architecture decisions this change relies on in `docs/adr/` (D-27):

- ADR-0001 `adr-0001-backend-python-fastapi.md` (D-02).
- ADR-0002 `adr-0002-identidad-keycloak.md` (D-03).
- ADR-0003 `adr-0003-api-gateway-nginx.md` (D-04).
- ADR-0004 `adr-0004-contenedor-y-base-logica-por-servicio.md` (D-05, D-06).
- ADR-0005 `adr-0005-arquitectura-hexagonal.md` (D-17, including D-33).

The other decisions this change applies (D-01, D-08 to D-16, D-19, D-20, D-32, D-34) are process or tooling
decisions recorded only in `docs/PLAN.md` section 5. Group 1 also waits for Integrante B's Antigravity
integration pull request (T-01), so that task 1.2 can verify Antigravity.

## Rule Applicability

- No glossary yet (the Event Storming produces it): artifacts use only terms from `openspec/config.yaml` and
  `docs/PLAN.md`.
- No role-authorization scenarios, except that the `ticketera` realm contains the three roles.
- No tactical DDD, integration events or concurrency/idempotency strategy until the first e1-* change.
- No API test collection or contract test task: the change adds no business endpoints (D-24).
- One ADR task: D-29 is an architecture decision this change implements (gateway routes), so its ADR is written
  here; the ADRs of D-23, D-24, D-25 and D-30 are written in the changes that implement them.

## Risks and Rollback

| Risk | Mitigation |
| --- | --- |
| An approved decision changes later (Event Storming, a Stage I design) | `/opsx:update` the artifacts before the affected group starts. |
| Groups 3 to 6 edit shared files in parallel | Each pull request adds only its own entries and rebases on `main`. |
| Groups 1 and 2 merge before the checks are required | Group 7 runs right after group 2 is merged; until then, reviewers do not approve a red pull request. |
| `docker compose up` fails on Windows with WSL 2 | Prevented in `design.md` and `CONTRIBUTE.md`; group 8 checks every member's machine. |
| A secret reaches the public repository | Review of every pull request; rotate any leaked value. |

Rollback: each group is one squash-merged pull request, so it is reverted with `git revert` of its commit.
Local state is removed with `docker compose down -v`. Ruleset changes (group 7) are undone in the repository
settings. Until archived, the change adds no specs to `openspec/specs/`.

## Impact

- Files: new `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTE.md`, `LICENSE`, `.gitignore`, `.editorconfig`, `.env.example`,
  `.github/` (CI workflow, pull request template, `CODEOWNERS`), `docker-compose.yml`, `infra/`, `services/`,
  `frontend/`, `docs/bitacora/`, the ADR of D-29 in `docs/adr/`; modified `.gitattributes` and
  `docs/adr/README.md` (index).
- APIs, through the gateway: `GET /api/<service>/health`, the gateway's `/healthz`, the identity service under
  `/auth`.
- Specs added under `openspec/specs/platform/` on archive: the seven capabilities listed above.
- Dependencies, inside containers: PostgreSQL, Keycloak, NGINX, Python with FastAPI, Node.js with React; tooling
  per D-15 and D-16.
- Systems: ruleset of `main`; every member needs Git and Docker Desktop with WSL 2 integration.
