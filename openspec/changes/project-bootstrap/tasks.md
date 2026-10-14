# Tasks

> **Gate:** groups 1 to 6 do not start until the approval pull request (`docs/PLAN.md` v0.4.0 with ADR-0001) is
> merged.
> **Dependencies:** 1 → 2 → 7 (right after 2 is merged) → 3, 4, 5, 6 (in parallel, after 2) → 8 (after 3 to 6)
> → 9 (last).
> Notation: `Req` = requirement of `specs/platform/<capability>`; `DS` = decision in `design.md`.

## 1. Conventions (A, feature/bootstrap-conventions)

- [ ] 1.1 Create one GitHub issue per task group (1 to 9) before any other work, so each group's pull request,
  this one included, closes its issue with `Closes #n` (Req contribution-workflow: Pull requests reference the
  issues they resolve; D-20). Verify: issue #n of this group closes when this pull request is merged.
- [ ] 1.2 Write `AGENTS.md` (DDD, TDD, Docker-only, conventions, branch and pull request rules) and `CLAUDE.md`
  importing it with `@AGENTS.md` (DS-22). Verify: Claude Code and OpenCode each list the rules when asked.
- [ ] 1.3 Write the contribution sections of `CONTRIBUTE.md` in Spanish: prerequisites (Git, Docker Desktop with
  WSL integration, clone inside the WSL file system), branch, commit and pull request flow (DS-17, DS-21).
  Verify: the reviewer follows it on this pull request.
- [ ] 1.4 Create the pull request template with the AI usage section and a checklist for branch name, test-first
  commits, Conventional Commits title and `Closes #n` (Req contribution-workflow: Every pull request declares AI
  usage; Behavior changes are committed test first; Pull request titles follow Conventional Commits; Pull requests
  reference the issues they resolve). Verify: the file is in this pull request; GitHub reads it from the base
  branch, so it is verified on the pull request of group 2 (task 2.20).
- [ ] 1.5 Create `CODEOWNERS` from PLAN 6.1, listing the three members by username for `docs/PLAN.md`,
  `docs/domain/` and `openspec/config.yaml` (Req contribution-workflow: Reviewers are requested automatically by
  path; DS-21). Verify: the file is in this pull request; GitHub reads it from the base branch, so it is verified
  on the pull request of group 2 (task 2.20).
- [ ] 1.6 Create `.gitignore` (`.env`, caches, `node_modules`, coverage) and the `.env.example` skeleton with its
  header comment (Req local-environment: Secrets are kept out of the repository). Verify: after copying
  `.env.example` to `.env`, `git status` does not list `.env`.
- [ ] 1.7 Update `.gitattributes` (explicit LF for `*.sh`, `*.sql`, `*.conf`, `Dockerfile`, `*.json`) and add
  `.editorconfig` (LF, final newline, indentation) (design Risks: CRLF). Verify: `git ls-files --eol` shows `lf`
  for every text file.
- [ ] 1.8 Add the MIT `LICENSE` (DS-22, D-11). Verify: GitHub shows the repository license as MIT.
- [ ] 1.9 Configure repository settings: squash merge only with "Default to pull request title", merge commit and
  rebase disabled, "Automatically delete head branches", "Require approval for first-time contributors" (DS-21,
  DS-18). Verify: screenshots recorded for the team log.
- [ ] 1.10 Review the ruleset of `main` against DS-21 (no bypass actors, one approval, approval of the most recent
  push, stale approvals dismissed, conversation resolution, deletion and force push blocked, up-to-date branches
  not required). Verify: exported ruleset JSON recorded for the team log.
- [ ] 1.11 Evidence: a direct push, a force push and a deletion of `main` are rejected, including for an
  administrator (Req contribution-workflow: Changes reach main only through pull requests). Verify: command outputs
  recorded for the team log.
- [ ] 1.12 Evidence on this pull request: self-approval does not count; a reviewer who pushes and approves stays
  blocked; a new commit dismisses the approval; an unresolved conversation blocks the merge; merge commit and
  rebase are unavailable; the branch is deleted after the squash merge (Req contribution-workflow: Merging requires
  approval from a member other than the author; The most recent push is approved by someone other than its pusher;
  Approvals are dismissed when new commits are pushed; Unresolved review conversations block the merge; Pull
  requests are integrated only by squash and merge). Verify: screenshots recorded for the team log.
- [ ] 1.13 Create `docs/bitacora/` with the weekly entry template and the entry for this group, including AI usage.
  Verify: the entry is in this pull request.

## 2. Platform (A, feature/bootstrap-platform)

- [ ] 2.1 Write the smoke test `tests/smoke/smoke-test.sh` (red): `/healthz` answers 200; realm discovery answers
  200 with the public issuer; `Host: evil.example` gets 421; `/auth/health`, `/auth/metrics` and
  `/api/unknown/health` get 404 (Req api-gateway: The gateway reports its own health; The gateway serves only the
  expected host names; Requests that match no route are rejected; Identity service health and metrics are never
  exposed; The identity service is served under /auth; Req continuous-integration: The smoke-test check verifies
  the running system through the gateway). Verify: the script fails against a repository with no system.
- [ ] 2.2 Extend the smoke test (red): derive the services from `docker compose config` (label
  `ticketera.health-path`; backends = services built from `./services/<name>`, failing when one lacks the label;
  backends are checked through the gateway at `/api/<service><health-path>`, and other labeled services, such as
  the frontend, on their own published port); only the gateway and the frontend publish ports, on `127.0.0.1`;
  every project container runs as non-root (Req continuous-integration: The smoke test covers every backend
  service the system starts; Req local-environment: Only the gateway and the frontend publish ports; Published
  ports are reachable only from the local machine; Containers run as a non-root user; DS-19). Verify: the script
  fails for each missing piece.
- [ ] 2.3 Write `tests/platform/database-isolation.sh` (red), run with `docker compose exec database psql`:
  cross-service connection rejected, role without grants rejected, `GRANT CONNECT` by a service role grants
  nothing, `CREATE DATABASE`, `CREATE ROLE` and `CREATE EXTENSION dblink` rejected, a service role can create a
  table in its own database (Req database-isolation: all requirements). Verify: the script fails before the
  database exists.
- [ ] 2.4 Write the realm check tests (red): a literal secret fails naming the field; a `${VAR}` placeholder
  passes; `clientAuthenticatorType: client-secret` passes (Req continuous-integration: The quality check rejects
  literal secrets in the realm definition; DS-20). Verify: the tests fail with no check script.
- [ ] 2.5 Implement the realm check script, inspecting JSON keys and run in a digest-pinned Python container
  (DS-20, DS-25). Verify: the tests of 2.4 pass.
- [ ] 2.6 Create the base `docker-compose.yml`: networks `edge` and `backend`, volume `ticketera-db-data`,
  `${VAR:?message}` for every required variable, default healthcheck values (10 s, 5 s, 3) (DS-01, DS-16, DS-23,
  DS-24; Req local-environment: Missing configuration stops startup with a clear error). Verify:
  `docker compose config` with an empty required variable fails and names it.
- [ ] 2.7 Add the database: `postgres:18-alpine` pinned by digest, volume at `/var/lib/postgresql`, `pg_isready`
  healthcheck, `backend` network only, no published port, `no-new-privileges`, `cap_drop: [ALL]` plus the minimal
  `cap_add` recorded (DS-12, DS-13, DS-24, DS-25). Verify: the container reaches healthy.
- [ ] 2.8 Write the init script in `infra/database/`: databases `catalog`, `sales`, `payments` and `keycloak`
  owned by the administrator; one `NOSUPERUSER NOCREATEDB NOCREATEROLE` role each with `CONNECT`+`TEMPORARY`,
  owner of its `public` schema; `CONNECT` revoked from `PUBLIC`; passwords from `.env`, added to `.env.example`
  (DS-02, DS-03). Verify: `tests/platform/database-isolation.sh` passes.
- [ ] 2.9 Write the realm definition `infra/keycloak/ticketera-realm.json` with the roles `ADMIN`, `EVENT_OWNER`
  and `CLIENT` and no secrets (Req identity-provisioning: The realm contains the platform roles; The realm
  definition contains no secrets). Verify: the realm check passes on it.
- [ ] 2.10 Add the identity service: Keycloak pinned by digest, `start-dev --import-realm`,
  `KC_HTTP_RELATIVE_PATH=/auth`, `KC_HOSTNAME`, `KC_HEALTH_ENABLED=true`, bootstrap administrator with
  `${VAR:?message}`, its own database role, `backend` network only, healthcheck with `bash /dev/tcp` on port 9000,
  `start_period: 120s`; try `cap_drop: [ALL]` (DS-04, DS-06, DS-13). Verify: healthy only after the realm is
  imported (otherwise switch the check to the discovery document); a restart keeps the realm (Req
  identity-provisioning: The ticketera realm is imported on startup; An existing realm is not overwritten on
  restart; Administrator credentials come from local configuration; The identity service is healthy only after the
  realm is available).
- [ ] 2.11 Add the gateway base: `nginxinc/nginx-unprivileged:1.28-alpine` pinned by digest, `server_name
  localhost 127.0.0.1`, `default_server` answering 421, `/healthz`, `include routes/*.conf`,
  `127.0.0.1:${GATEWAY_PORT}`, `edge` and `backend` networks, `wget` healthcheck, `no-new-privileges`,
  `cap_drop: [ALL]` (DS-07, DS-10, DS-12, DS-13, DS-23). Verify: the `/healthz`, 421 and port checks of the smoke
  test pass.
- [ ] 2.12 Write the forwarding test (red): a test-only compose file `tests/smoke/compose.echo.yml` adds an echo
  container (`traefik/whoami` pinned by digest) on the `backend` network and mounts a test-only gateway route to
  it; the smoke test sends forged `X-Forwarded-For`, `X-Forwarded-Host` and `X-Forwarded-Proto` and asserts that
  the echo receives exactly one address in `X-Forwarded-For`, which is not the forged value (with Docker port
  publishing the gateway sees the Docker bridge address, not `127.0.0.1`), and `X-Forwarded-Host` and
  `X-Forwarded-Proto` equal to the host and scheme actually used. The real system does not include the echo
  service, and it is not a backend for the coverage check (Req api-gateway: The gateway forwards the original
  client information; DS-08). Verify: the forwarding checks fail before 2.13.
- [ ] 2.13 Add the `/auth` route with replaced `X-Forwarded-*` headers, the explicit 404 for `/auth/health` and
  `/auth/metrics`, and the CORS map with `FRONTEND_ORIGIN` and `OPTIONS` answered with 204 under `/api/`; add
  `FRONTEND_ORIGIN` (default `http://localhost:5173`) to `.env.example`, since the gateway requires it with
  `${VAR:?message}` from this group on (DS-07, DS-08, DS-09). Verify: the forwarding checks of 2.12 pass; realm
  discovery through the gateway shows the public issuer; the admin console loads at `/auth/admin/`.
- [ ] 2.14 Run the whole platform locally with the test-only compose file. Verify: `tests/smoke/smoke-test.sh` and
  `tests/platform/database-isolation.sh` pass.
- [ ] 2.15 Create the CI workflow skeleton: triggers `pull_request` and `push` to `main`, `permissions: contents:
  read`, concurrency with `cancel-in-progress` only for pull requests, actions pinned by SHA; job
  `openspec-validate` with `@fission-ai/openspec@1.14.1` in a Node.js container (DS-18; Req continuous-integration:
  CI runs on every pull request to main; CI runs on every push to main; The openspec-validate check validates
  every OpenSpec artifact; The workflow token is read-only; Pull request code never runs with write permissions or
  secrets). Verify: the check is green on this pull request.
- [ ] 2.16 Add the `quality` job: build every image once with layer cache, run the realm check, and loop over the
  services derived from `docker compose config` for lint, type check and tests, naming service and step (Req
  continuous-integration: The quality check builds, lints, type checks and tests every service; CI uses no
  repository secrets; DS-18). Verify: the check is green on this pull request.
- [ ] 2.17 Add the `smoke-test` job: `.env` from `.env.example`, `up --wait --wait-timeout 300` with the test-only
  compose file of 2.12, smoke and database isolation scripts, logs of unhealthy containers on failure, `down -v`
  with `if: always()` (Req continuous-integration: The smoke test has a startup time limit; The smoke test leaves
  no state behind; DS-19). Verify: the check is green on this pull request.
- [ ] 2.18 Add the running and troubleshooting sections of `CONTRIBUTE.md`: first run, `up --build -V`, `down -v`,
  `restart gateway`, realm changes with "Partial export", bootstrap administrator created once, WSL pitfalls, and
  a note that groups 3, 5 and 6 all edit the gateway `depends_on` in `docker-compose.yml`, so each updates its
  branch from `main` before requesting review (DS-05, DS-17, design Risks). Verify: the reviewer starts the
  platform by following it.
- [ ] 2.19 Add the team log entry for this group, including AI usage. Verify: the entry is in this pull request.
- [ ] 2.20 Evidence: this pull request opens with the pull request template and requests the reviewer from
  `CODEOWNERS`, both read from `main` after group 1 (Req contribution-workflow: Every pull request declares AI
  usage; Reviewers are requested automatically by path). Verify: screenshots recorded for the team log.

## 3. catalog (B, feature/bootstrap-catalog)

- [ ] 3.1 Scaffold `services/catalog`: `pyproject.toml` and `uv.lock`, empty hexagonal packages, Dockerfile from
  a digest-pinned Python image with the environment in `/opt/venv`, UID/GID build arguments, non-root user,
  `PYTHONDONTWRITEBYTECODE=1` (DS-11, DS-13, DS-14, DS-25). Verify: the image builds and `id -u` in the container
  is not 0.
- [ ] 3.2 Write the tests of `/health` (red): 200 with exactly `status`, `service`, `database` within 1 s; 503
  with `unavailable` within 3 s when the database is unreachable; 200 again after recovery; HEAD with the same
  status code and no body; POST answers 405 (Req service-health: The health endpoint reports a healthy service;
  reports an unreachable database; requires no authentication; reveals no internal details; accepts only read
  requests). Verify: pytest fails.
- [ ] 3.3 Implement `/health` with `api_route` for GET and HEAD, `root_path=/api/catalog` and the `SELECT 1` probe
  with connect and query timeouts (DS-11). Verify: the tests of 3.2 pass.
- [ ] 3.4 Configure Ruff and mypy for the service. Verify: lint and type check pass in the container.
- [ ] 3.5 Add the compose entry: build `./services/catalog`, label `ticketera.health-path=/health`, `backend`
  network, depends on a healthy database, `urllib` healthcheck, bind mount with uvicorn reload on `0.0.0.0`,
  `no-new-privileges`, `cap_drop: [ALL]`; the gateway depends on a healthy `catalog` (DS-01, DS-12, DS-13, DS-17,
  DS-19). Verify: `docker compose up --wait` reaches healthy.
- [ ] 3.6 Add the CORS preflight checks for `/api/catalog/health` to the smoke test (red): the frontend origin is
  allowed and `catalog` does not receive the request; another origin gets no permission (Req api-gateway: The
  frontend can call the API from the browser). Verify: the smoke test fails without the route.
- [ ] 3.7 Add `infra/gateway/routes/catalog.conf` (Req api-gateway: Each backend service has one route; An
  unavailable service does not affect other routes). Verify: the smoke test passes, including the CORS checks.
- [ ] 3.8 Check that the files the tests generate in the mounted folder belong to the host user (Req
  local-environment: Files created in mounted folders belong to the host user). Verify: the host user deletes them
  without `sudo`.
- [ ] 3.9 Add the team log entry for this group, including AI usage. Verify: the entry is in this pull request.

## 4. Frontend and status page (B, feature/bootstrap-frontend)

- [ ] 4.1 Scaffold `frontend/`: React + TypeScript + Vite with `package-lock.json`, Dockerfile from a digest-pinned
  Node.js image, UID/GID build arguments, non-root user, Vite on `0.0.0.0` with the default `allowedHosts` and
  optional polling (DS-13, DS-15, DS-17, DS-25). Verify: the image builds and `id -u` is not 0.
- [ ] 4.2 Write the status page tests with Vitest and React Testing Library (red): all healthy; one 503; one 502;
  one request expiring after 5 s while the others are healthy; gateway unreachable shows every service unhealthy
  and the message (Req service-health: The status page shows the health of every backend service; Each health
  request of the status page has a time limit; The status page shows an unreachable gateway). Verify: Vitest
  fails.
- [ ] 4.3 Implement the status page with one `AbortController` per request and the API base URL from the
  environment (DS-15). Verify: the tests of 4.2 pass.
- [ ] 4.4 Configure ESLint and `tsc --noEmit`. Verify: both pass in the container.
- [ ] 4.5 Add the compose entry: `edge` network only, `127.0.0.1:${FRONTEND_PORT}`, `node_modules` as an anonymous
  volume, `wget` healthcheck, label `ticketera.health-path=/`, `no-new-privileges`, `cap_drop: [ALL]`; add
  `FRONTEND_PORT` to `.env.example` (DS-10, DS-13, DS-14, DS-23). Verify: the smoke test checks the frontend on its
  own published port, not through the gateway (which answers 404 for `/`), and it answers 200.
- [ ] 4.6 Add the team log entry for this group, including AI usage. Verify: the entry is in this pull request.

## 5. sales (C, feature/bootstrap-sales)

- [ ] 5.1 Scaffold `services/sales` as in 3.1 (DS-11, DS-13, DS-14, DS-25). Verify: the image builds and runs as
  non-root.
- [ ] 5.2 Write the tests of `/health` (red), as in 3.2 (Req service-health: health endpoint requirements).
  Verify: pytest fails.
- [ ] 5.3 Implement `/health` with `root_path=/api/sales` (DS-11). Verify: the tests of 5.2 pass.
- [ ] 5.4 Configure Ruff and mypy. Verify: both pass in the container.
- [ ] 5.5 Add the compose entry with label `ticketera.health-path=/health`, as in 3.5; the gateway depends on a
  healthy `sales` (DS-01, DS-12, DS-13, DS-17, DS-19). Verify: the smoke test fails until the route exists.
- [ ] 5.6 Add `infra/gateway/routes/sales.conf` (Req api-gateway: Each backend service has one route). Verify: the
  smoke test passes.
- [ ] 5.7 Check the ownership of files the tests generate in the mounted folder (Req local-environment: Files
  created in mounted folders belong to the host user). Verify: the host user deletes them without `sudo`.
- [ ] 5.8 Add the team log entry for this group, including AI usage. Verify: the entry is in this pull request.

## 6. payments (C, feature/bootstrap-payments)

- [ ] 6.1 Scaffold `services/payments` as in 3.1 (DS-11, DS-13, DS-14, DS-25). Verify: the image builds and runs
  as non-root.
- [ ] 6.2 Write the tests of `/health` (red), as in 3.2 (Req service-health: health endpoint requirements).
  Verify: pytest fails.
- [ ] 6.3 Implement `/health` with `root_path=/api/payments` (DS-11). Verify: the tests of 6.2 pass.
- [ ] 6.4 Configure Ruff and mypy. Verify: both pass in the container.
- [ ] 6.5 Add the compose entry with label `ticketera.health-path=/health`, as in 3.5; the gateway depends on a
  healthy `payments` (DS-01, DS-12, DS-13, DS-17, DS-19). Verify: the smoke test fails until the route exists.
- [ ] 6.6 Add `infra/gateway/routes/payments.conf` (Req api-gateway: Each backend service has one route). Verify:
  the smoke test passes.
- [ ] 6.7 Check the ownership of files the tests generate in the mounted folder (Req local-environment: Files
  created in mounted folders belong to the host user). Verify: the host user deletes them without `sudo`.
- [ ] 6.8 Add the team log entry for this group, including AI usage. Verify: the entry is in this pull request.

## 7. Required checks (A, no branch)

- [ ] 7.1 Right after group 2 is merged, mark `openspec-validate`, `quality` and `smoke-test` as required in the
  ruleset of `main` (Req contribution-workflow: Failing required checks block the merge; Req continuous-integration:
  Check names are stable). Verify: exported ruleset JSON recorded for the team log.
- [ ] 7.2 Evidence: a draft pull request with a failing test, and one with a pending check, cannot be merged; close
  them afterwards (Req contribution-workflow: Failing required checks block the merge). Verify: screenshots
  recorded for the team log.

## 8. Onboarding on a clean clone (A coordinates; A, B and C each run it, no branch)

- [ ] 8.1 Each member: clean clone inside WSL, `.env` from `.env.example`, `docker compose up`; every container
  healthy within 5 minutes after the build (Req local-environment: A single command starts the whole system;
  Containers wait for their dependencies to be healthy). Verify: time and output recorded per member.
- [ ] 8.2 Each member: the status page shows the three services healthy with no cross-origin error; the admin
  console opens at `/auth/admin/` with the credentials set at first start (Req api-gateway: The frontend can call
  the API from the browser; Req identity-provisioning: Administrator credentials come from local configuration).
  Verify: screenshots recorded per member.
- [ ] 8.3 Each member: a saved change in a backend service and in the frontend is served within 10 s; the tests of
  a service run through `docker compose` with no Python on the host (Req local-environment: Source changes are
  reflected without rebuilding; Project commands run inside containers). Verify: results recorded per member.
- [ ] 8.4 Each member: `docker compose down -v` and `up` recreate the databases and the realm; a plain restart
  keeps them (Req local-environment: A single command starts the whole system; Req identity-provisioning: The
  ticketera realm is imported on startup; An existing realm is not overwritten on restart). Verify: results
  recorded per member.
- [ ] 8.5 Each member: practice the OpenSpec workflow with `/opsx:onboard` only in a separate sandbox repository
  (`~/dev/openspec-sandbox`), never in this repository (PLAN 7.1 step 10). Verify: done recorded per member.

## 9. Verification and archive (A, feature/bootstrap-archive)

- [ ] 9.1 Commit the team log entries and evidence of groups 7 and 8 and tick their checkboxes. Verify: the entries
  and evidence are in this pull request.
- [ ] 9.2 Integration: a stopped service shows 502 on its route while the others answer, and appears unhealthy on
  the status page; its container reports unhealthy within 60 s; with the gateway stopped, the page shows every
  service unhealthy and the message (Req local-environment: Every container reports its health; Req api-gateway:
  An unavailable service does not affect other routes; Req service-health: status page requirements). Verify:
  results recorded for the team log.
- [ ] 9.3 Integration: this pull request, which changes only documentation and OpenSpec files, reports the three
  checks; the run log shows a read-only token; the CI on `main` ran after each squash merge; every run finished
  within 15 minutes (Req continuous-integration: Check names are stable; CI runs on every push to main; The
  workflow token is read-only; The CI finishes within 15 minutes). Verify: links recorded for the team log.
- [ ] 9.4 Record the completed bootstrap in the change log of `docs/PLAN.md` (section 11); this pull request then
  needs the approval of both other members (Req contribution-workflow: Shared planning files require approval
  from both other members). Verify: the pull request is merged only after both other members approve; screenshot
  recorded for the team log.
- [ ] 9.5 Run `openspec validate --all --strict` and `/opsx:verify project-bootstrap`. Verify: both pass.
- [ ] 9.6 Add the final team log entry, stating which member completed each group. Verify: the entry is in this
  pull request.

## Workflow follow-up

- After task 9.6, archive the change with `/opsx:archive project-bootstrap` on `feature/bootstrap-archive`, in the
  same pull request, before it is merged (PLAN 7.1 step 11).
- Fixes found during onboarding (group 8) get their own `feature/` branch and pull request.
