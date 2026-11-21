# Spec Delta

## Purpose

The token-claims contract of `e1-identity-access` (design, "Token-Claims Contract for Services"), copied as written,
as that design asks every feature change to do. In `catalog` it applies to the management API under
`/manage/events`; the public catalog ignores tokens (spec `catalog/event-browsing`).

## ADDED Requirements

### Requirement: Services take roles only from the platform roles in realm_access.roles

A service SHALL treat a user as holding only those of `ADMIN`, `EVENT_OWNER` and `CLIENT` that appear in the
token's `realm_access.roles` claim. It SHALL ignore every other role in that claim and any role found in any
other claim.

#### Scenario: Default roles of the identity service

- **WHEN** a service receives a token whose `realm_access.roles` contains `CLIENT`, `offline_access`,
  `uma_authorization` and `default-roles-ticketera`
- **THEN** the service treats the user as holding only the `CLIENT` role

#### Scenario: Role in another claim

- **WHEN** a service receives a token whose `realm_access.roles` contains only `CLIENT` and whose other claims
  mention `ADMIN`
- **THEN** the service does not treat the user as holding the `ADMIN` role

#### Scenario: Token without realm roles

- **WHEN** a service receives a token with no `realm_access.roles` claim
- **THEN** the service treats the user as holding no platform role

### Requirement: Services identify the user only from the token

A service SHALL take the user's identity and roles only from the bearer token in the `Authorization` header, and
SHALL ignore any user identity or role that the client sends in another header, the query string or the body.
A service that records data for a user, such as the orders of a `CLIENT` in `sales`, SHALL key it by `sub`.

#### Scenario: Forged identity header

- **WHEN** the `CLIENT` test user sends a request with its token and an `X-User-Id` header naming another user
- **THEN** the service handles the request as the user identified by the token's `sub`

#### Scenario: Forged role in the body

- **WHEN** the `CLIENT` test user sends a request with its token and a body that claims the `ADMIN` role
- **THEN** the service handles the request as a user holding only the `CLIENT` role

### Requirement: Services authorize by role

A service SHALL answer `403 Forbidden` to a request whose token does not hold a role that the endpoint requires,
without performing the operation, and SHALL answer `401 Unauthorized` to a request to a protected endpoint that
carries no bearer token.

#### Scenario: CLIENT calls an ADMIN-only endpoint

- **WHEN** the `CLIENT` test user calls an endpoint that requires the `ADMIN` role
- **THEN** the service answers `403 Forbidden` and performs no operation

#### Scenario: EVENT_OWNER calls an ADMIN-only endpoint

- **WHEN** the `EVENT_OWNER` test user calls an endpoint that requires the `ADMIN` role
- **THEN** the service answers `403 Forbidden` and performs no operation

#### Scenario: ADMIN calls an ADMIN-only endpoint

- **WHEN** the `ADMIN` test user calls an endpoint that requires the `ADMIN` role
- **THEN** the service handles the request and answers a `2xx` status

#### Scenario: Protected endpoint reached without a token

- **WHEN** a request without a bearer token reaches a protected endpoint of a service
- **THEN** the service answers `401 Unauthorized` and performs no operation

### Requirement: Services trust the token validated by the gateway

A service SHALL read the claims of a bearer token by decoding its payload, relying on the gateway having
validated the token, without checking its signature or calling the identity service. It SHALL answer
`401 Unauthorized` when the payload cannot be decoded.

#### Scenario: Valid token forwarded by the gateway

- **WHEN** a service receives a request with a token that the gateway has validated
- **THEN** the service reads `sub` and `realm_access.roles` from it without any request to the identity service

#### Scenario: Payload that cannot be decoded

- **WHEN** a service receives a request to a protected endpoint whose bearer token has a payload that is not
  valid JSON
- **THEN** the service answers `401 Unauthorized` and performs no operation

### Requirement: Services never expose or accept tokens outside the Authorization header

A service MUST NOT write the `Authorization` header or any token to its logs, and MUST NOT accept a token from the
query string.

#### Scenario: Request with a token is logged

- **WHEN** a service handles a request with a bearer token
- **THEN** no line the service writes to its logs contains the token

#### Scenario: Token in the query string

- **WHEN** a request to a protected endpoint carries a token only in its query string
- **THEN** the service answers `401 Unauthorized` and performs no operation
