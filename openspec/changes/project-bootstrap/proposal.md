# Proposal

## Why

The team cannot start Stage I features until it shares a contribution workflow and a system that already runs:
today the repository only holds the OpenSpec setup and `docs/PLAN.md`. This change establishes both, so every
later change (e1-*, e2-*, e3-*) is reviewed the same way and added on top of a walking skeleton that CI proves
works end to end (PLAN.md sections 6, 7.1 and 7.1.1).

## What Changes

- Contribution rules and conventions: `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTE.md`, pull request template,
  `CODEOWNERS`, `.gitignore`, `.env.example`, MIT `LICENSE` (D-11); update of the existing `.gitattributes`
  (initial commit).
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
  database connectivity, reachable through the gateway.
- Frontend status page that shows the health of every service through the gateway.
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
- No messaging, cache or Stage II/III containers (RabbitMQ, Redis, recommendation, search, sales-queue).
- No HTTP request log middleware (change `e1-request-log`).
- No glossary, context map or Event Storming results; no ADR-0002.
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
| 6 | `payments` skeleton | C | `feature/bootstrap-payments` |
| 7 | Required status checks in the ruleset; runs right after group 2 is merged | A | none (settings only) |
| 8 | Onboarding on a clean clone (A coordinates; A, B and C each run it) | A | none |
| 9 | Verification and archive; commits the evidence of groups 7 and 8 | A | `feature/bootstrap-archive` |

Any fix found during onboarding gets its own branch and pull request.

## Prerequisites

Groups 1 to 6 do not start until the approval pull request (`docs/PLAN.md` v0.4.0) is merged. It sets
the technical decisions D-01 to D-06, D-12 and D-15 to D-17, and the process decisions that group 1 applies
(D-08, D-09, D-10, D-11, D-13, D-19 and D-20), to Approved and records them in `docs/adr/ADR-0001`. Until then
these decisions are proposed, and this change implements nothing.

## Rule Applicability

- No glossary yet (the Event Storming produces it): artifacts use only terms from `openspec/config.yaml` and
  `docs/PLAN.md`.
- No role-authorization scenarios, except that the `ticketera` realm contains the three roles.
- No tactical DDD, integration events or concurrency/idempotency strategy until the first e1-* change.

## Risks and Rollback

| Risk | Mitigation |
| --- | --- |
| A gated decision changes at the team meeting | `/opsx:update` the artifacts before implementation starts. |
| Groups 3 to 6 edit shared files in parallel | Each pull request adds only its own entries and rebases on `main`. |
| Groups 1 and 2 merge before the checks are required | Group 7 runs right after group 2 is merged; until then, reviewers do not approve a red pull request. |
| `docker compose up` fails on Windows with WSL 2 | Prevented in `design.md` and `CONTRIBUTE.md`; group 8 checks every member's machine. |
| A secret reaches the public repository | Review of every pull request; rotate any leaked value. |

Rollback: each group is one squash-merged pull request, so it is reverted with `git revert` of its commit.
Local state is removed with `docker compose down -v`. Ruleset changes (group 7) are undone in the repository
settings. Until archived, the change adds no specs to `openspec/specs/`.

## Impact

- Files: new `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTE.md`, `LICENSE`, `.gitignore`, `.env.example`, `.github/`
  (CI workflow, pull request template, `CODEOWNERS`), `docker-compose.yml`, `infra/`, `services/`, `frontend/`,
  `docs/bitacora/`; modified `.gitattributes`.
- APIs, through the gateway: `GET /api/<service>/health`, the gateway's `/healthz`, the identity service under
  `/auth`.
- Specs added under `openspec/specs/platform/` on archive: the seven capabilities listed above.
- Dependencies, inside containers: PostgreSQL, Keycloak, NGINX, Python with FastAPI, Node.js with React; tooling
  per D-15 and D-16.
- Systems: ruleset of `main`; every member needs Git and Docker Desktop with WSL 2 integration.
