# Proposal

## Why

The walking skeleton has the `ticketera` realm with its roles, but no client can sign in and the gateway forwards
every request without checking who sends it. Stage I needs authentication and roles (PLAN 7.3, D-28) before the
feature changes can protect their endpoints, and ADR-0003 left the token validation mechanism to this change.

## What Changes

- **Realm** (`infra/keycloak/ticketera-realm.json`):
  - A public client for the frontend: Authorization Code with PKCE (`S256`), redirect URIs and web origins
    limited to the frontend's address, no direct access grants, and access tokens that carry `sub` and
    `realm_access.roles`.
  - A mapper that puts the realm roles in the frontend's ID token.
  - A client `ticketera-api-tests` with direct access grants, used only by API tests.
  - One test user per role (`ADMIN`, `EVENT_OWNER`, `CLIENT`), whose passwords are `${VAR}` placeholders filled
    from `.env`.
  - Direct access grants turned off for the built-in `admin-cli` client.
  - The realm display name "GoPass" (D-38).
- **Realm secret check** (`scripts/check_realm_secrets.py`): accepts `${VAR}` placeholders in user credentials
  and still rejects literal values, as the existing `platform/continuous-integration` requirement already states.
- **Gateway: protected by default.** **BREAKING**: every route that is not public needs a valid bearer token,
  checked with the identity service before the request is forwarded:
  - The check covers routes outside `/api/`, such as the smoke-test echo route, and every route added later,
    which inherits it without declaring it.
  - No `Bearer <token>` header, or a token that the identity service rejects: `401 Unauthorized`.
  - Identity service unreachable or too slow: `502 Bad Gateway` within 5 seconds.
  - Public paths, which skip the check: `GET` and `HEAD` on `/api/<service>/health` (the services accept both)
    and everything under `/auth/`. Health keeps answering while the identity service is down.
  - The CORS preflight (`OPTIONS`) is answered without a token.
- **Gateway: upstream failures handled once.** The connect timeout and the mapping of upstream failures to `502`
  move from each route file to the server, and `/auth/` gets timeouts.
- **Gateway: CORS preflight** also allows the methods and the `Authorization`, `Content-Type` and
  `Idempotency-Key` headers the frontend sends.
- **Gateway: no tokens in logs.** The gateway never writes a token to its log, and a token in the query string is
  never accepted.
- **Token-claims contract for services**, defined in `design.md`; each feature change adds it to its own spec and
  tests it on its endpoints, following the D-33 skeleton:
  - `sub` identifies the user, and is the `CLIENT` identity in sales.
  - Roles come from `realm_access.roles`, filtered to `ADMIN`, `EVENT_OWNER` and `CLIENT`.
  - Services decode the token payload without checking its signature, because only the gateway can reach them.
  - Services never log the `Authorization` header, and public endpoints never read identity.
- **Frontend**, built on PR #20:
  - The base with Tailwind CSS, shadcn/ui and the GoPass tokens (D-16, D-38), as a separate task group.
  - A router, sign-in through the identity service (Authorization Code with PKCE), the callback, silent token
    renewal and sign-out.
  - Routes guarded by session (`RequireAuth`) and by role (`RequireRole`), with an access-denied page. The app
    has no admin page; Vitest tests the role guard with a test-only component.
  - A minimal "My account" page at `/account`, guarded by session, that shows the signed-in user's name and
    platform roles.
  - API calls to protected routes carry `Authorization: Bearer <access token>`.
  - The status page stays public and calls the public health routes without a token.
  - Mockups of the sign-in flow, the header with the signed-in user and the sign-out action, the "My account"
    page and the access-denied page.
- **Tests**:
  - Smoke-test extensions: `401` cases, public health, the echo route with a token, preflight headers, and
    identity down giving `502` while health stays `200`.
  - Realm checks.
  - Vitest tests for the frontend.
  - A Bruno collection in `tests/api/identity/` (D-24). Its CI runner and the ADR of D-24 belong to the first
    Stage I change with FastAPI endpoints (PLAN 7.3). Until that runner exists, the collection runs locally with
    a command documented in `CONTRIBUTE.md`; it runs in CI once the runner exists.
- **Docs**:
  - ADR-0007, token validation at the gateway (written as a task of this change; see Impact).
  - `CONTRIBUTE.md`: test users, signing in, and `docker compose down -v` after realm changes.
  - The team log.

## Non-goals

- Role checks at the gateway: the gateway authenticates (`401`); each service authorizes (`403`).
- Signature checks in services.
- Caching identity service answers at the gateway.
- Self-registration.
- A custom theme for the identity service's pages.
- TLS or a production mode for the identity service.
- The `403` endpoints and role rules of each feature: each feature change adds them, following the D-33
  skeleton.
- The correlation id and the service request log (`e1-request-log`).
- An OpenAPI contract test: this change adds no FastAPI endpoint.

## Capabilities

### New Capabilities

- `identity/access-token`: the claims every access token of the `ticketera` realm carries: `sub`, which
  identifies the user, and `realm_access.roles`, which lists the user's platform roles. How services read them is
  the token-claims contract in `design.md`, which each feature change adds to its own spec.
- `identity/user-authentication`: how a person signs in to and out of the frontend, how the session is renewed,
  and how routes are guarded by session and by role.

### Modified Capabilities

These specs exist only in the unarchived `project-bootstrap` change, so this change is archived after it.

- `platform/api-gateway`:
  - "Each backend service has one route": forwards only authenticated requests and public paths, instead of
    every request.
  - "The frontend can call the API from the browser": the preflight allows the methods and headers the frontend
    sends.
  - New requirements: protected by default, public paths, identity service unavailable, and no tokens in logs.
- `platform/identity-provisioning`:
  - New requirements: the frontend client, the API test client and the test users.
  - "The realm definition contains no secrets": user passwords appear only as `${VAR}` placeholders.

`platform/continuous-integration` does not change: its requirement on literal secrets in the realm definition
already lets `${VAR}` placeholders pass, so making the realm secret check accept them in user credentials is an
implementation task tested against that requirement.

## Impact

- **Bounded contexts:** identity (realm, token contract, sign-in) and the platform gateway. catalog, sales and
  payments get no code changes now; they adopt the token contract in their own feature changes.
- **Owner:** Eduardo (team member A). Issue #28: `Refs #28` in the planning pull request, `Closes #28` in the
  implementation pull request (D-37).
- **Code:**
  - `infra/keycloak/ticketera-realm.json` and `scripts/check_realm_secrets.py` with its fixtures.
  - `infra/gateway/templates/default.conf.template`, `infra/gateway/routes/identity.conf` and the smoke-test
    files.
  - `docker-compose.yml`: `KC_PROXY_HEADERS` and the test user passwords; `.env.example`: their placeholders.
  - `frontend/`: new dependencies (router, OIDC client, Tailwind CSS, shadcn/ui, `@fontsource`).
  - `CONTRIBUTE.md` and the team log.
- **Files owned by other members:**
  - `infra/gateway/routes/catalog.conf` (B), `sales.conf` and `payments.conf` (C): their
    `proxy_connect_timeout` and `error_page` lines move to the server.
  - CODEOWNERS: B reviews `/infra/`, `docker-compose.yml` and `.env.example`; C reviews `/frontend/`.
- **Coordination with `e1-request-log` (B):**
  - Both changes edit the gateway template, so the second one to merge rebases on the first.
  - A `401` from the gateway never reaches a service, so an authentication failure can be logged only by the
    gateway (PLAN 4.6).
- **Other feature changes:** their API tests get tokens from `ticketera-api-tests` and the test users.
- **Team log:** closes the pending item of group 3, where to handle the `502` of `sales` and `payments`: it moves
  to the server level of the gateway.
- **ADR:** ADR-0007 (token validation at the gateway with `auth_request` and `userinfo`) is a task of this
  change, written with the `create-architectural-decision-record` skill; `design.md` links it (D-27). No ADR
  file is written during planning.

### Process note

The Stage I changes start in parallel, by team decision of 08/11/2026. `docs/PLAN.md` 7.3 still says that
order-2 changes wait until the design of `e1-idempotent-purchase` is merged; a separate pull request updates
that text. Only the service code that reads tokens depends on the D-33 skeleton, and this change writes none.

## Risks and rollback

- **Every protected request calls the identity service.** That adds latency and makes the identity service a
  dependency of every protected route. The gateway answers `502` within 5 seconds when it is down, and health
  stays public. Caching is the later optimization (non-goal).
- **Trust in the gateway.** Services do not check signatures, so a compromised container on the backend network
  could send them forged tokens. Only the gateway and the frontend publish ports, and the smoke test enforces
  it. The design records the residual risk; signature checks in services are the later upgrade path.
- **The realm is imported only once.** Restarting the identity service never re-imports the realm, so each
  member needs `docker compose down -v` to get the new clients and users. `CONTRIBUTE.md` says so.
- **New required variables in `.env`.** The test user passwords become required values, so Compose stops for a
  member who has not copied them from `.env.example`. `CONTRIBUTE.md` and a message to the team cover it.
- **Moved route lines.** A route file that keeps its own `error_page` stops inheriting the server's, so that
  route answers `500` instead of `502` when the identity service is down. The smoke-test checks for a stopped
  service and for the identity service down catch it.
- **Rollback:**
  - Revert the squash commit of the implementation pull request on `main`, which restores the open gateway, the
    previous realm and the frontend of PR #20.
  - Each member then runs `docker compose down -v` to re-import the previous realm.
  - No other service's data or schema changes.
