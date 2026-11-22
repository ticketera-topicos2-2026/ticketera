# Tasks

> **Priority:** `P1` = in the delivery of 2026-11-25, which is the pull request of group 1. `P2` = after
> 2026-11-25, still required to close Stage I (D-28): the React screens, the API test collection and the latency
> measurement. Moving the screens after 2026-11-25 is pending the team's confirmation. The course deliverable
> E-03 asks for mockups, functional APIs and unit tests (`docs/PLAN.md` 2.4); D-28 requires the screens to close
> Stage I, which group 2 does.
> **Dependencies:** 1 → 2 → 3. Group 2 starts from `main` once group 1 is merged.
> **Pull requests:** group 1 and group 2 are one branch and one pull request each; both carry `Refs #28`, and the
> one merged last, group 2, also carries `Closes #28` (D-37). Group 3 runs in the pull request of group 2.
> Within each group every test task comes before its implementation task.
> **Commits:** each red test task is committed as `test(...)` before the `feat(...)` or `fix(...)` that makes it
> pass (RB-12).
> Notation: `Req` = requirement of the spec named after it (`specs/identity/<capability>` or
> `specs/platform/<capability>`; `continuous-integration` is the spec of `project-bootstrap`); `IA` = decision in
> `design.md`. This change adds no FastAPI endpoint, so it has no OpenAPI contract test (proposal, Non-goals).

## 1. Backend (A, feature/e1-identity-access-backend)

- [x] 1.1 [P1] Write the realm secret check tests (red): new fixtures for a user credential whose `value` is a
  `${NAME}` placeholder (passes), an exported hash with `secretData` and `credentialData` (fails, naming the
  field) and a placeholder with a default (fails); `literal-user-credentials.json` keeps failing (Req
  continuous-integration: The quality check rejects literal secrets in the realm definition - Scenario: Realm
  definition with a placeholder; IA-12). Verify: the placeholder fixture fails with today's script.
- [x] 1.2 [P1] Make `scripts/check_realm_secrets.py` read each object of a `credentials` list field by field:
  `value` must be exactly a placeholder, and any key other than `type`, `value`, `temporary` and `userLabel` is a
  literal (IA-12). Verify: the tests of 1.1 and the existing ones pass with
  `python -I -B -m unittest discover -s tests/platform`; the check passes on the current realm.
- [x] 1.3 [P1] Write `tests/platform/test_realm_definition.py` (red, `unittest`): the frontend client is public,
  code flow only, PKCE `S256`, exact redirect URIs `${FRONTEND_ORIGIN}/signin-callback` and
  `${FRONTEND_ORIGIN}/silent-callback`, web origin `${FRONTEND_ORIGIN}`, post-logout URI `${FRONTEND_ORIGIN}/`, no
  direct grants, no lightweight tokens, realm roles mapped to the ID token; `ticketera-api-tests` is public, direct
  grants only, access token lifespan 60 s; `admin-cli` has direct grants off; `registrationAllowed` is false;
  `displayName` is "GoPass"; three test users with email, first and last name, `emailVerified`, no required
  actions, one platform role each and a placeholder password (Req identity-provisioning: The realm has a client for
  the frontend - Scenario: Frontend address changed in local configuration; Tokens of the frontend client carry the
  user's identity and roles; The realm has a client for API tests; The built-in admin client of the realm allows no
  password grant; The realm has one test user per platform role; Users cannot register themselves; The sign-in page
  carries the GoPass name; The realm definition contains no secrets - Scenario: Test user passwords in the realm
  definition; IA-10, IA-11, IA-18). Verify: the tests fail on the current realm.
- [x] 1.4 [P1] Create `tests/smoke/identity-checks.sh`, sourced by `smoke-test.sh`, with a helper that gets tokens
  from `ticketera-api-tests` (scope `openid`, passwords from the Compose configuration), and write its realm client
  checks (red): password grant refused with `unauthorized_client` for the frontend client and for `admin-cli` of
  `ticketera`; `admin-cli` of `master` still issues the administrator's token; authorization requests of the
  frontend client without `code_challenge`, with `plain` and with a redirect URI outside `FRONTEND_ORIGIN`
  rejected; authorization request of `ticketera-api-tests` rejected; token endpoint CORS allowed for
  `FRONTEND_ORIGIN` and not for another origin; sign-in page shows "GoPass" and not `ticketera`; registration
  address shows no form (Req identity-provisioning: The realm has a client for the frontend - all scenarios except
  the changed address; The realm has a client for API tests - Scenario: Browser sign-in with the API test client;
  The built-in admin client of the realm allows no password grant - both scenarios; Users cannot register
  themselves - both scenarios; The sign-in page carries the GoPass name; IA-17). Verify: the checks fail against
  the current realm.
- [x] 1.5 [P1] Write the user and token checks in `identity-checks.sh` (red): each test user gets a token with the
  password from `.env` and holds only its role (which also proves no extra first sign-in step); wrong password
  gives `invalid_grant`; `sub` non-empty, equal after sign-in, sign-out (form `POST` to the logout endpoint with
  the refresh token) and sign-in, and different between `CLIENT` and `EVENT_OWNER`; the `sub` of an example access
  token of the frontend client from the admin API's scope evaluation equals the `sub` of an API test token of the
  same user; example ID and access tokens of the frontend client carry `realm_access.roles`; the user session
  address from the admin API is the address the gateway received, with and without a forged `X-Forwarded-For`;
  `docker compose config` with one test password unset fails and names it (Req identity-provisioning: The realm
  definition contains no secrets - Scenario: Imported test user password; Tokens of the frontend client carry the
  user's identity and roles - both scenarios; The realm has a client for API tests - Scenarios: Token for an API
  test, Wrong password; The realm has one test user per platform role - all scenarios; The identity service sees
  the client's address - both scenarios; Req access-token: The access token identifies the user - all scenarios;
  The access token carries the user's platform roles - all scenarios). Verify: the checks fail against the current
  realm and Compose file.
- [x] 1.6 [P1] Write the realm in `infra/keycloak/ticketera-realm.json`: `ticketera-frontend` with its ID-token
  roles mapper, `ticketera-api-tests`, `admin-cli` without direct grants, `displayName`, `registrationAllowed`, the
  three test users with complete profiles and `${TEST_USER_<ROLE>_PASSWORD}` placeholders (IA-10, IA-11, IA-18).
  Verify: the tests of 1.3 and the realm secret check pass.
- [x] 1.7 [P1] Pass `FRONTEND_ORIGIN` and the three `TEST_USER_<ROLE>_PASSWORD` variables to the identity service
  with `${VAR:?message}`, set `KC_PROXY_HEADERS=xforwarded`, add the placeholders to `.env.example`, and give the
  frontend `VITE_OIDC_AUTHORITY` and `VITE_OIDC_CLIENT_ID` (IA-09, IA-11). Verify: after `docker compose down -v`
  and `up --wait`, the checks of 1.4 and 1.5 pass.
- [x] 1.8 [P1] Write the access check tests in `identity-checks.sh` (red), and make the existing forwarding checks
  of `smoke-test.sh` send a token: a control that an API test token with `openid` gets `200` from `userinfo`;
  `401` with `WWW-Authenticate: Bearer` without a token, with `Basic`, with `Bearer x` and with an altered payload;
  an expired token (obtained at the start of the script, checked last); the token of a signed-out session; a token
  issued without `openid`; a token only in the query string; each test user's token forwarded with
  `Authorization` unchanged through the echo route; `GET /api/sales/example` with a token answered by `sales`; the
  echo route without a token gets `401`; `/healthz` gets `200` and `/api/unknown/example` gets `404` without a
  token; concurrent requests of two users through the echo route each carry their own header; two `Authorization`
  headers get `400`; paths that only look public get `401` without a token, sent as written:
  `/api/sales/healthx`, `/api/sales/heal%74h`, `/api/sales/health%2F`, `/api/sales/%2e%2e/sales/health`,
  `/api/sales/../sales/health` and `/auth/../api/sales/example`. The `401` and `400` cases go through the echo
  route, which answers every request it receives with `200`, and the paths that look public go to `sales`, which
  never answers `401`, so no check reads a service log (Req api-gateway: Each backend service has one
  route - Scenario: Authenticated request routed to the sales service; Requests forwarded on paths that are not
  public require a valid access token - all scenarios except Route added later; A token rejected by the identity
  service is answered 401; A request with more than one Authorization header is rejected; Tokens are accepted only
  in the Authorization header; Public paths skip the access check - Scenario: Path that only starts like a health
  path; IA-03). Verify: every check that depends on the access check fails.
- [x] 1.9 [P1] Add the test-only route `tests/smoke/gateway/latency.conf` (`/api/smoke-latency/` to the echo
  service, declaring nothing about access) and write the public path tests (red): `GET` and `HEAD` on health
  without a token; health with `Bearer x` answers as without a token; the realm discovery document without a token
  gets `200`; `POST /api/sales/health`, `GET /api/sales/health/` and `GET /api/sales/health/extra` without a token
  get `401`; `/api/smoke-latency/example` without a token gets `401` (Req api-gateway: Public paths skip the access
  check - all scenarios; Requests forwarded on paths that are not public require a valid access token - Scenario:
  Route added later; IA-03, IA-17). Verify: the `401` checks fail before 1.10.
- [x] 1.10 [P1] Implement the access check in the gateway template: `auth_request /_auth` at server level; the
  internal `/_auth` location with the public map on `$request_method` and `$request_uri`, the local `401`, every
  `userinfo` 4xx mapped to `401`, no body, `GET`, cleared `Content-Type` and `Cookie`, the forwarding snippet;
  `auth_request off` in `location /auth/` of `identity.conf`; exactly one `WWW-Authenticate` challenge on every
  `401`; and a check in `identity-checks.sh` that a valid token with `PUT` (with a body) and `DELETE` through the
  echo route gets `200` (IA-01 to IA-04, IA-09). Verify: the checks of 1.8 (except the expired token, which needs
  1.6 too) and 1.9 pass; the bootstrap checks of `smoke-test.sh` still pass.
- [ ] 1.11 [P1] Write the identity-unavailable tests at the end of `identity-checks.sh` (red): with the identity
  service stopped, a protected request with a token gets `502` in under 5 s and does not reach the service; the
  discovery document gets `502` in under 5 s; `Basic` and no-token requests still get `401`; `/api/sales/health`
  and `/healthz` get `200`; then the identity service is started and waited healthy (Req api-gateway: An
  unavailable identity service is answered 502 - all scenarios; Requests forwarded on paths that are not public
  require a valid access token - Scenario: Authorization header that is not a bearer token). Verify: the `502`
  checks fail (routes answer `500`, `/auth/` waits 60 s).
- [ ] 1.12 [P1] Set connect 1 s and read 3 s in `/_auth` and `/auth/`; move `proxy_connect_timeout 3s` and
  `error_page 500 502 504 =502 @upstream_unavailable` to server level, and remove them and the named locations from
  `catalog.conf`, `sales.conf` and `payments.conf` (IA-05, IA-06). Verify: the checks of 1.11 and the existing
  stopped-service checks pass.
- [ ] 1.13 [P1] Write the CORS tests (red): a preflight of `/api/sales/example` from `FRONTEND_ORIGIN` without a
  token, asking for `DELETE` and `authorization`, `content-type`, `idempotency-key`, gets `204` allowing them and
  does not reach `sales`; a `401` to the frontend's origin carries `Access-Control-Allow-Origin` (Req api-gateway:
  The frontend can call the API from the browser - Scenarios: CORS preflight from the frontend's address; Rejected
  request from the frontend's address). Verify: the `Allow-Methods` and `Allow-Headers` checks fail.
- [ ] 1.14 [P1] Add the preflight maps and `add_header ... always` for `Access-Control-Allow-Methods` and
  `Access-Control-Allow-Headers` (IA-07). Verify: the checks of 1.13 and the existing CORS checks pass.
- [ ] 1.15 [P1] Write the log tests (red): after the other checks, `docker compose logs gateway` contains none of
  the tokens used, including a query-string token sent while the identity service is stopped and a sign-out
  request under `/auth/` with `id_token_hint` in its query string (Req api-gateway: The gateway never writes a
  token to its logs - all scenarios). Verify: the query-string and `id_token_hint` checks fail with the `main`
  format.
- [ ] 1.16 [P1] Define `log_format ticketera` without query string or referrer, use it for `access_log`, set
  `error_log ... crit`, and write the rule for `e1-request-log` in a comment (IA-08). Verify: the checks of 1.15
  pass.
- [ ] 1.17 [P1] Run the whole system locally with the echo overlay. Verify: `smoke-test.sh --require-echo`
  (identity checks included), `database-isolation.sh` and the `tests/platform` tests pass; then the `quality`,
  `smoke-test` and `openspec-validate` checks are green on the pull request and the CI stays within 15 minutes.
- [ ] 1.18 [P1] Draw low-fidelity mockups in `docs/mockups/identity/` with the GoPass palette (D-38): the sign-in
  flow, the header with the signed-in user and the sign-out action, the "My account" page and the access-denied
  page; they guide the screens of group 2. Verify: the mockups are in the pull request and the reviewer sees each
  screen of `specs/identity/user-authentication`.
- [ ] 1.19 [P1] Write ADR-0007 (token validation at the gateway with `auth_request` and `userinfo`, services
  trusting the forwarded token) with the `create-architectural-decision-record` skill, add it to the index in
  `docs/adr/README.md`, and fix the link in `design.md` if the number or slug changed (D-27; IA-01). Verify: the
  ADR is in the pull request and the link resolves.
- [ ] 1.20 [P1] Write the `CONTRIBUTE.md` section (Spanish): the test users and their roles, the four new `.env`
  variables, `docker compose down -v` after realm changes, and getting a token from `ticketera-api-tests`.
  Verify: a reviewer follows it from a fresh clone.
- [ ] 1.21 [P1] Write the team log entry for this group with the red and green evidence, the closed pending item
  of group 3 (502 handling at server level) and the AI usage. Verify: the entry is in the pull request.
- [ ] 1.22 [P1] After the merge, send the team message: copy the four `TEST_USER_*_PASSWORD` lines to `.env` and
  run `docker compose down -v` before `up`. Verify: the message is linked in the team log.
- [x] 1.23 [P1] Extend `tests/platform/test_realm_definition.py` (red) to a second EVENT_OWNER test user,
  `test-other-event-owner`: exactly four test users, this one with a complete profile, no required actions, only
  `EVENT_OWNER` and the placeholder `${TEST_USER_OTHER_EVENT_OWNER_PASSWORD}` (Req identity-provisioning: The realm
  has a second EVENT_OWNER test user - Scenario: Second EVENT_OWNER test user; The realm definition contains no
  secrets - Scenario: Test user passwords in the realm definition; IA-11). Verify: only the new and changed tests
  fail on the current realm; every other test of `tests/platform` still passes.
- [x] 1.24 [P1] Refactor `identity-checks.sh` so that it looks up a test user's token by username and password
  variable instead of by platform role, with no change of behavior (IA-17). Verify: the full smoke test with the
  echo overlay and `--require-echo` is green, as before the refactor.
- [x] 1.25 [P1] Add smoke checks to `identity-checks.sh` (red): `test-other-event-owner` gets a token with its
  password and holds only `EVENT_OWNER`; its `sub` differs from that of `test-event-owner`; `docker compose config`
  with `TEST_USER_OTHER_EVENT_OWNER_PASSWORD` empty fails and names it (Req identity-provisioning: The realm has a
  second EVENT_OWNER test user - all scenarios; IA-11). Verify: only these new checks fail; every pre-existing check
  still passes.
- [x] 1.26 [P1] Add `test-other-event-owner` to the realm, pass `TEST_USER_OTHER_EVENT_OWNER_PASSWORD` to the
  identity service with `${VAR:?message}` and add it to `.env.example` (IA-11). Verify: after `docker compose
  down -v` and `up --wait`, the tests of 1.23 and the checks of 1.25 pass and the full smoke test is green.
- [ ] 1.27 [P1] Make `tests/api/run.sh` and `tests/smoke/measure-catalog-latency.sh` get real tokens from
  `ticketera-api-tests` (password grant, `openid` scope, passwords from `docker compose config`): `run.sh` gets the
  tokens of `test-event-owner`, `test-other-event-owner`, `test-admin` and `test-client` right before Bruno runs, as
  `ownerToken`, `otherOwnerToken`, `adminToken` and `clientToken`; the latency script renews the owner's token when
  less than 15 s of it is left (IA-18). When a token request fails, either script stops at once with a message that
  names the username, and neither ever prints a password or a token. `run.sh` runs its `docker compose` commands
  from the repository root, so a relative `COMPOSE_FILE` works. Verify: `run.sh sales`, run first on the database
  left by the `down -v` of 1.26, is reported for information; then the static tests, the full smoke test with
  `--require-echo`, `run.sh catalog` and `run.sh platform` pass, and the latency script, run last, passes.
  Afterwards `run.sh catalog` test 10 is expected to fail until the next `docker compose down -v`: the public
  catalog sorts by `starts_at`, so the latency events push the new event out of the first 100 (known issue,
  reported to Ariel, not changed here).

## 2. Frontend and API tests (A, feature/e1-identity-access-frontend)

- [ ] 2.1 [P2] Install the GoPass base inside the frontend container: Tailwind CSS 4 with `@tailwindcss/vite`, the
  D-38 palette, gradient, radii and fonts as `@theme` tokens, shadcn/ui initialized with the `@/` alias, exact
  versions in `package.json` and the lockfile (IA-16, D-16, DS-25). Verify: `npm ci`, lint, type check, build and
  the existing Vitest tests pass in the container; the status page renders with the tokens.
- [ ] 2.2 [P2] Add the shadcn/ui components the screens use (button, card, alert, avatar or similar), inside the
  container (IA-16). Verify: lint, type check and build pass.
- [ ] 2.3 [P2] Write the tests (red): the status page renders at `/` without starting a sign-in, and still renders
  every service when the discovery request fails; the header shows a sign-in action and no user name to an
  anonymous user (Req user-authentication: The status page stays public - both scenarios; The frontend shows who is
  signed in - Scenario: Anonymous user). Verify: the tests fail with no router or provider.
- [ ] 2.4 [P2] Add React Router (declarative mode), the layout with the header, and the `AuthProvider` with one
  `UserManager`, an in-memory user store and background initialization, configured from `VITE_OIDC_AUTHORITY` and
  `VITE_OIDC_CLIENT_ID` (IA-13, IA-14). Verify: the tests of 2.3 and the existing ones pass.
- [ ] 2.5 [P2] Write the sign-in tests (red): an anonymous user opening `/account` is sent to the identity service
  with `/account` as return address and comes back there; a non-relative return address leads to `/`; the callback
  with `access_denied` shows the error and a retry and leaves no session; a callback that matches no sign-in shows
  the error and leaves no session; the callback removes `code` and `state` from the address (Req
  user-authentication: A person signs in through the identity service - all scenarios). Verify: the tests fail.
- [ ] 2.6 [P2] Implement `signIn(returnTo)` and the `/signin-callback` route (IA-13). Verify: the tests of 2.5 pass.
- [ ] 2.7 [P2] Write the guard and page tests (red): the `CLIENT` user sees "My account" with its name and only the
  `CLIENT` role; the `ADMIN` user sees only `ADMIN`; default roles are not shown; an anonymous user does not see
  `/account` and no protected API call is made; with a test-only component behind `RequireRole("ADMIN")`, `CLIENT`
  and `EVENT_OWNER` see the access-denied page and no API call of that component is made, `ADMIN` sees it, and an
  anonymous user is sent to sign in; the header shows the signed-in user's name and a sign-out action (Req
  user-authentication: Pages are guarded by session - both scenarios; Pages are guarded by role - all scenarios;
  The "My account" page shows the signed-in user - all scenarios; The frontend shows who is signed in - Scenario:
  Signed-in user). Verify: the tests fail.
- [ ] 2.8 [P2] Implement `RequireAuth`, `RequireRole`, the access-denied page, the role filter on the ID token's
  `realm_access.roles`, the "My account" page at `/account` and the signed-in header, following the mockups.
  Verify: the tests of 2.7 pass.
- [ ] 2.9 [P2] Write the API call tests (red): a protected call carries `Authorization: Bearer` and the current
  access token; the status page's health calls carry no `Authorization` header, for an anonymous and a signed-in
  user; a `401` clears the session and starts a sign-in with the current page as return address; several
  concurrent `401` answers start it once (Req user-authentication: API calls carry the access token only where it
  is needed - all scenarios; A rejected token ends the frontend session - both scenarios). Verify: the tests fail.
- [ ] 2.10 [P2] Implement `apiFetch` with the single-flight `401` handling. Verify: the tests of 2.9 pass.
- [ ] 2.11 [P2] Write the sign-out tests (red): signing out removes the user from memory and submits a form `POST`
  to the end-session endpoint with `id_token_hint`, `client_id` and `post_logout_redirect_uri` in the body; no URL
  requested contains a token; the user ends on a public page with no session (Req user-authentication: Signing out
  ends the session at the identity service - Scenarios: User signs out, No token in the sign-out address). Verify:
  the tests fail.
- [ ] 2.12 [P2] Implement `signOut()` with the hidden form `POST` (IA-15). Verify: the tests of 2.11 pass.
- [ ] 2.13 [P2] Write the renewal tests (red): when the access token is about to expire, a new one is obtained,
  the page stays as it was and the next call carries it; when renewal fails, the session is cleared and a sign-in
  starts (Req user-authentication: The session is renewed without interrupting the user - both scenarios).
  Verify: the tests fail.
- [ ] 2.14 [P2] Enable refresh-token renewal 60 s before expiry and handle its failure (IA-14). Verify: the tests
  of 2.13 pass.
- [ ] 2.15 [P2] Write the reload tests (red): after a reload, the provider runs a silent sign-in and restores the
  session; when it fails, a public page stays as it is with no prompt, and a protected page starts a sign-in
  (IA-14). Verify: the tests fail.
- [ ] 2.16 [P2] Implement the silent sign-in in a hidden frame with the `/silent-callback` route, and the fallback
  to a top-level redirect with `prompt=none` (IA-14). Verify: the tests of 2.15 pass.
- [ ] 2.17 [P2] Write the Bruno runner and the token part of the collection: `tests/api/package.json` and its
  lockfile pinning `@usebruno/cli`; `tests/api/identity/` with a `local` environment that reads the passwords from
  environment variables; requests for a token per test user with tests for `sub` and `realm_access.roles` (Req
  access-token: The access token identifies the user - Scenario: Token of a signed-in user; The access token
  carries the user's platform roles - all scenarios; IA-19); document in `CONTRIBUTE.md` the command that runs it
  in a digest-pinned Node container. Verify: the collection passes with that command.
- [ ] 2.18 [P2] Add the gateway requests to the Bruno collection: a protected path without a token and with
  `Bearer x` gets `401`; public health without a token gets `200` (Req api-gateway: Requests forwarded on paths
  that are not public require a valid access token - Scenarios: Request without a token, Malformed or tampered
  token; Public paths skip the access check - Scenario: Service health without a token). Verify: the collection
  passes with the documented command.
- [ ] 2.19 [P2] Write `tests/smoke/measure-access-check-latency.sh`: 10 warm-up and 100 sequential requests to
  `/api/smoke-latency/example` with a token and to `/api/smoke-latency/health`, printing both medians and their
  difference; run it locally and record the result in the team log (Req api-gateway: The access check adds little
  latency). Verify: the difference is 30 ms or less; if not, open a follow-up for an `upstream` with `keepalive`
  (design, Risks).
- [ ] 2.20 [P2] Write the sign-in steps in `CONTRIBUTE.md` (Spanish) and the team log entry for this group with
  the red and green evidence, the latency result and the AI usage. Verify: lint, type check, Vitest and build pass
  in the container; the entry is in the pull request.

## 3. Closing (A, in the pull request merged last)

- [ ] 3.1 [P2] Record the browser evidence in the team log: sign-in from `/account` and back to it; sign-out ends
  the identity session, so the next sign-in asks for credentials (Req user-authentication: A person signs in
  through the identity service - Scenario: Anonymous user opens a protected page; Signing out ends the session at
  the identity service - Scenario: Protected page after signing out). Verify: screenshots or a recording in the
  team log.
- [ ] 3.2 [P2] Run `openspec validate e1-identity-access --strict` and tick every finished task. Verify: the change
  is valid and the pull request carries `Closes #28`.
- [ ] 3.3 [P2] Record the remaining browser evidence: silent sign-in after a reload, and a changed
  `FRONTEND_ORIGIN` after `docker compose down -v` (Req identity-provisioning: The realm has a client for the
  frontend - Scenario: Frontend address changed in local configuration). Verify: screenshots in the team log.

## Workflow follow-up

- Archive the change only after `project-bootstrap` is archived: the MODIFIED deltas of `platform/api-gateway`
  and `platform/identity-provisioning` need those specs in `openspec/specs/`.
- `docs/PLAN.md` 7.3 is updated in its own pull request for the parallel start of Stage I.
- Feature changes copy the token-claims contract of `design.md` into their specs and test it on their endpoints.
