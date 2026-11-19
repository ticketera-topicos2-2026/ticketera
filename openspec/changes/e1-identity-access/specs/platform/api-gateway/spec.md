# Spec Delta

## MODIFIED Requirements

### Requirement: Each backend service has one route

The gateway SHALL forward every request under `/api/<service>/` that its access check lets through to that
backend service, with the `/api/<service>` prefix removed and the status code and body of the response unchanged.

#### Scenario: Request routed to the catalog service

- **WHEN** a client sends `GET /api/catalog/health` to the gateway
- **THEN** the `catalog` service receives `GET /health` and the client gets its status code and body unchanged

#### Scenario: Request routed to the payments service

- **WHEN** a client sends `GET /api/payments/health` to the gateway
- **THEN** the `payments` service receives `GET /health`

#### Scenario: Authenticated request routed to the sales service

- **WHEN** the `CLIENT` test user sends `GET /api/sales/example` to the gateway with a valid access token
- **THEN** the `sales` service receives `GET /example` with the same `Authorization` header, and the client gets
  its status code and body unchanged

### Requirement: The frontend can call the API from the browser

The frontend, loaded in a browser from its own address, SHALL be able to call the API routes and receive their
responses, error responses included, without cross-origin errors; no other origin SHALL be granted cross-origin
access. The gateway SHALL answer a CORS preflight itself, without a token, allowing the methods `GET`, `HEAD`,
`POST`, `PUT`, `PATCH` and `DELETE` and the headers `Authorization`, `Content-Type` and `Idempotency-Key`.

#### Scenario: Status page loads the health of every service

- **WHEN** a team member opens the frontend status page in a browser on the local machine
- **THEN** the page receives the health response of every backend service with no cross-origin error in the
  browser

#### Scenario: CORS preflight from the frontend's address

- **WHEN** a browser sends a CORS preflight `OPTIONS /api/sales/example` without a token from the frontend's
  address, asking for the method `DELETE` and the headers `authorization`, `content-type` and `idempotency-key`
- **THEN** the preflight is answered successfully, the response allows the frontend's address as origin, that
  method and those headers, and the `sales` service does not receive the request

#### Scenario: CORS preflight from another origin

- **WHEN** a browser sends a CORS preflight `OPTIONS /api/catalog/health` from any address other than the
  frontend's
- **THEN** the response grants no permission to that origin: it neither allows every origin nor echoes the
  requested origin

#### Scenario: Rejected request from the frontend's address

- **WHEN** a browser at the frontend's address sends `GET /api/sales/example` without a token
- **THEN** the gateway answers `401 Unauthorized` with the frontend's address as allowed origin, so the frontend
  can read the status

## ADDED Requirements

### Requirement: Requests forwarded on paths that are not public require a valid access token

The gateway SHALL forward a request on a path that is not public only when it carries
`Authorization: Bearer <token>` with a token that the identity service accepts, and SHALL otherwise answer
`401 Unauthorized` with a `WWW-Authenticate: Bearer` header, without forwarding it. This SHALL hold for every
route that forwards, including routes outside `/api/` and routes added later that declare nothing about access.
Requests the gateway answers by itself SHALL keep their behavior without a token.

#### Scenario: Request without a token

- **WHEN** a client sends `GET /api/sales/example` without an `Authorization` header
- **THEN** the gateway answers `401 Unauthorized` with `WWW-Authenticate: Bearer`, and the `sales` service does
  not receive the request

#### Scenario: Authorization header that is not a bearer token

- **WHEN** a client sends `GET /api/sales/example` with `Authorization: Basic dXNlcjpwYXNz`
- **THEN** the gateway answers `401 Unauthorized` without sending any request to the identity service

#### Scenario: Expired token

- **WHEN** a client sends `GET /api/sales/example` with an access token that has expired
- **THEN** the gateway answers `401 Unauthorized` and the `sales` service does not receive the request

#### Scenario: Malformed or tampered token

- **WHEN** a client sends `GET /api/sales/example` with `Authorization: Bearer x`, or with a valid access token
  whose payload has been altered
- **THEN** the gateway answers `401 Unauthorized` and the `sales` service does not receive the request

#### Scenario: Token reused after signing out

- **WHEN** the `CLIENT` test user signs out and a client then sends `GET /api/sales/example` with that user's
  previous access token
- **THEN** the gateway answers `401 Unauthorized`

#### Scenario: Valid token of any platform role

- **WHEN** the `ADMIN`, `EVENT_OWNER` or `CLIENT` test user sends `GET /api/sales/example` with a valid access
  token
- **THEN** the gateway forwards the request whatever the role, and the `sales` service receives the
  `Authorization` header unchanged

#### Scenario: Route outside /api/

- **WHEN** a client sends a request without a token to the test-only echo route of the smoke test
- **THEN** the gateway answers `401 Unauthorized` and the echo service does not receive the request

#### Scenario: Route added later

- **WHEN** a route file for a new backend service is added without any access setting, and a client sends a
  request without a token to a path of that route other than its health path
- **THEN** the gateway answers `401 Unauthorized`

#### Scenario: Gateway health without a token

- **WHEN** a client sends `GET /healthz` without a token
- **THEN** the gateway answers `200 OK`

#### Scenario: Path that matches no route, without a token

- **WHEN** a client sends `GET /api/unknown/example` without a token
- **THEN** the gateway answers `404 Not Found`, not `401 Unauthorized`

#### Scenario: Concurrent requests of different users

- **WHEN** the `CLIENT` and `EVENT_OWNER` test users send requests to the same route at the same time, each with
  its own valid access token
- **THEN** each forwarded request carries the `Authorization` header of its own sender

### Requirement: A token rejected by the identity service is answered 401

The gateway SHALL answer `401 Unauthorized` to every request whose token the identity service rejects, whatever
status the identity service uses to reject it, and MUST NOT pass that status on to the client.

#### Scenario: Token without the openid scope

- **WHEN** a client sends `GET /api/sales/example` with an access token of the `ticketera` realm that was issued
  without the `openid` scope
- **THEN** the gateway answers `401 Unauthorized`, not `403 Forbidden`

### Requirement: Public paths skip the access check

The gateway SHALL forward `GET` and `HEAD` requests to `/api/<service>/health`, and every request under `/auth/`,
without checking any token, and SHALL forward them the same way whether they carry a token or not, valid or not.
Any other method or path SHALL be subject to the access check.

#### Scenario: Service health without a token

- **WHEN** a client sends `GET /api/catalog/health` without a token
- **THEN** the `catalog` service answers it and the client gets its status code

#### Scenario: HEAD on service health without a token

- **WHEN** a client sends `HEAD /api/payments/health` without a token
- **THEN** the `payments` service answers it and the client gets its status code

#### Scenario: Health with a malformed token

- **WHEN** a client sends `GET /api/sales/health` with `Authorization: Bearer x`
- **THEN** the client gets the same status code and body as for the same request without a token

#### Scenario: Identity service path without a token

- **WHEN** a client sends `GET /auth/realms/ticketera/.well-known/openid-configuration` without a token
- **THEN** the response is `200 OK`

#### Scenario: Other method on the health path

- **WHEN** a client sends `POST /api/sales/health` without a token
- **THEN** the gateway answers `401 Unauthorized` and the `sales` service does not receive the request

#### Scenario: Path that only starts like a health path

- **WHEN** a client sends `GET /api/sales/health/` or `GET /api/sales/health/extra` without a token
- **THEN** the gateway answers `401 Unauthorized`

### Requirement: An unavailable identity service is answered 502

When the identity service does not answer, the gateway SHALL answer `502 Bad Gateway` within 5 seconds to every
request that needs the access check and to every request under `/auth/`, without forwarding protected requests,
and SHALL keep serving the public health paths and its own health.

#### Scenario: Protected request while the identity service is stopped

- **WHEN** the identity service is stopped and a client sends `GET /api/sales/example` with an access token
  obtained before
- **THEN** the gateway answers `502 Bad Gateway` within 5 seconds and the `sales` service does not receive the
  request

#### Scenario: Identity service path while it is stopped

- **WHEN** the identity service is stopped and a client sends
  `GET /auth/realms/ticketera/.well-known/openid-configuration`
- **THEN** the gateway answers `502 Bad Gateway` within 5 seconds

#### Scenario: Service health while the identity service is stopped

- **WHEN** the identity service is stopped and a client sends `GET /api/sales/health`
- **THEN** the `sales` service answers it normally

#### Scenario: Gateway health while the identity service is stopped

- **WHEN** the identity service is stopped and a client sends `GET /healthz`
- **THEN** the gateway answers `200 OK`

### Requirement: A request with more than one Authorization header is rejected

The gateway SHALL answer `400 Bad Request` to any request that carries more than one `Authorization` header,
without forwarding it.

#### Scenario: Two Authorization headers

- **WHEN** a client sends `GET /api/catalog/health` with the headers `Authorization: Bearer a` and
  `Authorization: Bearer b`
- **THEN** the gateway answers `400 Bad Request` and the `catalog` service does not receive the request

### Requirement: Tokens are accepted only in the Authorization header

The gateway SHALL take a token only from the `Authorization` header and MUST NOT accept a token sent in the query
string.

#### Scenario: Token in the query string

- **WHEN** a client sends `GET /api/sales/example?access_token=<valid access token>` without an `Authorization`
  header
- **THEN** the gateway answers `401 Unauthorized` and the `sales` service does not receive the request

### Requirement: The gateway never writes a token to its logs

The gateway MUST NOT write an access token, an ID token or a refresh token to its logs, whether the token arrives
in a header or in the query string.

#### Scenario: Requests with a token

- **WHEN** clients send requests with valid and invalid access tokens in the `Authorization` header
- **THEN** no line of the gateway logs contains any of those tokens

#### Scenario: Token in the query string

- **WHEN** a client sends `GET /api/sales/example?access_token=<valid access token>`
- **THEN** no line of the gateway logs contains that token

#### Scenario: Sign-out address with an ID token

- **WHEN** a client sends a sign-out request under `/auth/` whose query string contains `id_token_hint=<ID token>`
- **THEN** no line of the gateway logs contains that ID token

### Requirement: The access check adds little latency

On a development machine with every service healthy, the median response time of 100 sequential authenticated
requests to a protected path SHALL exceed the median of 100 sequential requests to a public path of the same
route and backend by 30 ms or less.

#### Scenario: Latency measured on a development machine

- **WHEN** a team member sends 100 sequential authenticated requests to a protected path and 100 sequential
  requests to a public path of the same route and backend, after 10 warm-up requests to each
- **THEN** the difference between the two median response times is 30 ms or less
