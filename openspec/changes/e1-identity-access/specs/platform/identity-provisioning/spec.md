# Spec Delta

## MODIFIED Requirements

### Requirement: The realm definition contains no secrets

The realm definition stored in the repository MUST NOT contain passwords, client secrets or private keys. Each
value that must be secret, such as a test user's password, SHALL appear only as an environment variable
placeholder (`${NAME}`) whose value comes from `.env`.

#### Scenario: Reviewer reads the realm definition

- **WHEN** a reviewer reads the realm definition in the repository
- **THEN** it contains no password, client secret or private key

#### Scenario: Test user passwords in the realm definition

- **WHEN** a reviewer reads the test users in the realm definition
- **THEN** each password is an environment variable placeholder, not a literal value

#### Scenario: Imported test user password

- **WHEN** the identity service imports the realm and the `CLIENT` test user signs in
- **THEN** the sign-in succeeds with the password set in `.env` for that user

## ADDED Requirements

### Requirement: The realm has a client for the frontend

The `ticketera` realm SHALL contain a public client for the frontend that signs users in only with the
authorization code flow and PKCE with the `S256` method, accepts only redirect addresses under the frontend's
address (`FRONTEND_ORIGIN` in `.env`), grants cross-origin access only to that address, and does not allow the
password grant.

#### Scenario: Redirect address outside the frontend

- **WHEN** an authorization request of the frontend client asks to redirect to an address outside
  `FRONTEND_ORIGIN`
- **THEN** the identity service rejects the request and does not redirect to that address

#### Scenario: Authorization request without PKCE

- **WHEN** an authorization request of the frontend client has no `code_challenge`
- **THEN** the identity service rejects the request

#### Scenario: Authorization request with the plain PKCE method

- **WHEN** an authorization request of the frontend client uses `code_challenge_method=plain`
- **THEN** the identity service rejects the request

#### Scenario: Password grant with the frontend client

- **WHEN** a client requests a token from the frontend client with the password grant and the `CLIENT` test
  user's credentials
- **THEN** the identity service answers with the error `unauthorized_client` and issues no token

#### Scenario: Token request from the frontend's address

- **WHEN** a browser at `FRONTEND_ORIGIN` exchanges an authorization code of the frontend client for tokens
- **THEN** the response allows `FRONTEND_ORIGIN` as origin

#### Scenario: Token request from another origin

- **WHEN** a browser at an address other than `FRONTEND_ORIGIN` sends a token request of the frontend client
- **THEN** the response grants no permission to that origin

#### Scenario: Frontend address changed in local configuration

- **WHEN** a team member sets another port in `FRONTEND_ORIGIN` and starts the system after
  `docker compose down -v`
- **THEN** the frontend client accepts redirect addresses and grants cross-origin access under the new address
  only

### Requirement: Tokens of the frontend client carry the user's identity and roles

Access tokens issued to the frontend client SHALL be complete: they SHALL carry `sub` and `realm_access.roles` as
required by `identity/access-token`. The ID token issued to the frontend client SHALL also carry the user's realm
roles in `realm_access.roles`.

#### Scenario: Access token of the frontend client

- **WHEN** the `EVENT_OWNER` test user signs in through the frontend client
- **THEN** the access token contains `sub` and a `realm_access.roles` claim that contains `EVENT_OWNER`

#### Scenario: ID token of the frontend client

- **WHEN** the `EVENT_OWNER` test user signs in through the frontend client
- **THEN** the ID token contains a `realm_access.roles` claim that contains `EVENT_OWNER` and neither `ADMIN` nor
  `CLIENT`

### Requirement: The realm has a client for API tests

The `ticketera` realm SHALL contain a client named `ticketera-api-tests` that issues tokens to the test users with
the password grant, for API tests only, and that cannot be used to sign in through a browser.

#### Scenario: Token for an API test

- **WHEN** an API test requests a token from `ticketera-api-tests` with the password grant, the `openid` scope and
  the `CLIENT` test user's credentials
- **THEN** the identity service issues an access token that contains `sub` and a `realm_access.roles` claim
  that contains `CLIENT`

#### Scenario: Wrong password

- **WHEN** an API test requests a token from `ticketera-api-tests` with the `CLIENT` test user's name and a wrong
  password
- **THEN** the identity service answers with the error `invalid_grant` and issues no token

#### Scenario: Browser sign-in with the API test client

- **WHEN** a browser sends an authorization request of `ticketera-api-tests`
- **THEN** the identity service rejects the request

### Requirement: The built-in admin client of the realm allows no password grant

The built-in `admin-cli` client of the `ticketera` realm MUST NOT issue tokens with the password grant, so that
only the project's clients issue tokens to the realm's users.

#### Scenario: Password grant with admin-cli in the ticketera realm

- **WHEN** a client requests a token from `admin-cli` of the `ticketera` realm with the password grant and the
  `CLIENT` test user's credentials
- **THEN** the identity service answers with the error `unauthorized_client` and issues no token

#### Scenario: Administrator of the master realm

- **WHEN** a team member requests a token from `admin-cli` of the `master` realm with the administrator
  credentials
- **THEN** the identity service issues the token as before

### Requirement: The realm has one test user per platform role

The `ticketera` realm SHALL contain one test user for each of `ADMIN`, `EVENT_OWNER` and `CLIENT`, each holding
only that platform role, able to sign in with the password set in `.env` without any extra step. Startup SHALL
stop when one of those passwords is missing.

#### Scenario: ADMIN test user

- **WHEN** the `ADMIN` test user signs in
- **THEN** the sign-in succeeds and the user holds the `ADMIN` role and no other platform role

#### Scenario: EVENT_OWNER test user

- **WHEN** the `EVENT_OWNER` test user signs in
- **THEN** the sign-in succeeds and the user holds the `EVENT_OWNER` role and no other platform role

#### Scenario: CLIENT test user

- **WHEN** the `CLIENT` test user signs in
- **THEN** the sign-in succeeds and the user holds the `CLIENT` role and no other platform role

#### Scenario: First sign-in needs no extra step

- **WHEN** a test user signs in for the first time after the realm is imported
- **THEN** the identity service asks for no password change, email verification or profile update

#### Scenario: Test user password missing

- **WHEN** the password of one test user is missing from `.env` or empty
- **THEN** startup stops before any container starts and the error names the missing value

### Requirement: The realm has a second EVENT_OWNER test user

The `ticketera` realm SHALL contain a second test user holding only `EVENT_OWNER`, distinct from the `EVENT_OWNER`
test user, so that API tests can check that an `EVENT_OWNER` cannot reach the events of another one. It SHALL sign
in with the password set in `.env` without any extra step, and startup SHALL stop when that password is missing.

#### Scenario: Second EVENT_OWNER test user

- **WHEN** the second `EVENT_OWNER` test user signs in
- **THEN** the sign-in succeeds and the user holds the `EVENT_OWNER` role and no other platform role

#### Scenario: Two different EVENT_OWNER test users

- **WHEN** the `EVENT_OWNER` test user and the second `EVENT_OWNER` test user sign in
- **THEN** their access tokens have different `sub` values

#### Scenario: Second EVENT_OWNER password missing

- **WHEN** the password of the second `EVENT_OWNER` test user is missing from `.env` or empty
- **THEN** startup stops before any container starts and the error names the missing value

### Requirement: Users cannot register themselves

The `ticketera` realm MUST NOT let anyone create an account from the sign-in page.

#### Scenario: Sign-in page

- **WHEN** an anonymous user opens the sign-in page of the `ticketera` realm
- **THEN** the page offers no way to register

#### Scenario: Registration address

- **WHEN** a client opens the registration address of the `ticketera` realm directly
- **THEN** the identity service creates no account and shows no registration form

### Requirement: The identity service sees the client's address

The identity service SHALL take the client address from the forwarding headers the gateway sets, so that what it
records about a request names the client's address and not the gateway's.

#### Scenario: Sign-in recorded with the client's address

- **WHEN** the `CLIENT` test user signs in from a browser on the local machine
- **THEN** the identity service records the sign-in with the address the gateway received the request from, not
  the gateway's own address

#### Scenario: Forged forwarding header

- **WHEN** a client signs in through the gateway with a forged `X-Forwarded-For` header
- **THEN** the identity service records the client's real address and not the forged value

### Requirement: The sign-in page carries the GoPass name

The sign-in pages of the `ticketera` realm SHALL show "GoPass" as the realm's name.

#### Scenario: Sign-in page title

- **WHEN** an anonymous user opens the sign-in page of the `ticketera` realm
- **THEN** the page shows "GoPass", and not `ticketera`, as the realm's name
