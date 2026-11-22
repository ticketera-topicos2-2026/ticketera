# Spec Delta

## ADDED Requirements

### Requirement: Every backend service writes one log line per request

The `catalog`, `sales` and `payments` services SHALL write exactly one request log line to standard output for
every HTTP request they receive, after the response status is known, whatever that status is.

#### Scenario: Successful request

- **WHEN** a client sends `GET /api/catalog/health` through the gateway and the service answers `200 OK`
- **THEN** the `catalog` service writes exactly one request log line for that request, with status `200`

#### Scenario: Request rejected by the service's access rules

- **WHEN** the `CLIENT` test user calls a `sales` endpoint that requires the `ADMIN` role
- **THEN** the service answers `403 Forbidden` and writes one request log line with status `403` and the user's
  `sub`

#### Scenario: Token whose payload cannot be decoded

- **WHEN** a request reaches a protected endpoint of a service with a bearer token whose payload is not valid
  JSON
- **THEN** the service answers `401 Unauthorized` and writes one request log line with status `401` and a `null`
  user

#### Scenario: Validation error

- **WHEN** a request reaches an endpoint with a body that fails validation
- **THEN** the service writes one request log line with the status it answered, such as `400` or `422`

#### Scenario: Path that matches no route of the service

- **WHEN** a request reaches a service on a path it does not define
- **THEN** the service answers `404 Not Found` and writes one request log line with a `null` route

#### Scenario: Unhandled error in an endpoint

- **WHEN** an endpoint raises an unexpected exception
- **THEN** the service answers `500 Internal Server Error` and writes one request log line with status `500`

#### Scenario: Concurrent requests

- **WHEN** 50 requests reach the same service at the same time, from different users
- **THEN** the service writes 50 complete request log lines, none of them mixed with another, each with the
  correlation id and user of its own request

### Requirement: The request log line has a fixed set of fields

A service request log line SHALL be a single JSON object on one line with exactly these fields: `timestamp`
(RFC 3339, UTC, millisecond precision), `service` (the service name), `correlation_id`, `method`, `route`
(the route template that matched, without the public prefix, or `null`), `status` (integer), `duration_seconds`
(number, millisecond precision) and `user_id` (the token's `sub`, or `null`). Every service SHALL write the same
fields with the same names and types.

#### Scenario: Fields of a request log line

- **WHEN** a client sends `GET /api/payments/health` through the gateway
- **THEN** the `payments` log line for it is valid JSON with exactly the fields `timestamp`, `service`
  (`payments`), `correlation_id`, `method` (`GET`), `route` (`/health`), `status` (`200`), `duration_seconds`
  and `user_id` (`null`)

#### Scenario: Route template instead of the requested path

- **WHEN** the `CLIENT` test user sends `POST /api/sales/events/7f3c9a/orders` through the gateway
- **THEN** the `route` field is `/events/{event_id}/orders`, and the line does not contain `7f3c9a`

#### Scenario: Same schema in every service

- **WHEN** the request log lines of `catalog`, `sales` and `payments` are checked against the shared request log
  JSON Schema
- **THEN** every line of the three services passes

### Requirement: The logged user is the token's sub

The `user_id` field SHALL be the `sub` claim of the bearer token that the service's authentication accepted for
the request, and SHALL be `null` when the request carries no token, when the service could not read one, or when
the endpoint does not authenticate. A user identity sent in any other header, the query string or the body MUST
NOT be logged as `user_id`.

#### Scenario: Authenticated request

- **WHEN** the `CLIENT` test user calls an authenticated `sales` endpoint with a valid access token
- **THEN** the log line has `user_id` equal to that user's `sub`

#### Scenario: Forged identity header

- **WHEN** the `CLIENT` test user sends a request with its token and an `X-User-Id` header naming another user
- **THEN** the log line has `user_id` equal to the `sub` of the `CLIENT` test user

#### Scenario: Public endpoint

- **WHEN** a client sends `GET /api/sales/health` with a valid access token
- **THEN** the log line has a `null` `user_id`, because the health endpoint does not authenticate

### Requirement: The duration covers the whole handling of the request

The `duration_seconds` field SHALL measure the time from the moment the service receives the request, before
authentication, until the whole response has been sent, so that it includes authentication, the endpoint and
the serialization and sending of the response.

#### Scenario: Slow endpoint

- **WHEN** a test endpoint that takes 200 ms is called
- **THEN** its log line has a `duration_seconds` of at least `0.2` and less than `0.4`

#### Scenario: Rejected authentication is timed too

- **WHEN** a service rejects a request with `401 Unauthorized`
- **THEN** its log line has a `duration_seconds` greater than or equal to `0`

### Requirement: The request log never contains sensitive data

A request log line MUST NOT contain any field other than those of the fixed set. In particular it MUST NOT
contain an access token, an ID token or a refresh token, the `Authorization` or `Cookie` headers, any other
request or response header, the query string, the request or response body, or payment data.

#### Scenario: Request with a token

- **WHEN** a client sends a request with a valid access token to any service
- **THEN** no line written by the service contains the token or any part of its signature

#### Scenario: Token in the query string

- **WHEN** a request to a service carries `?access_token=<valid access token>`
- **THEN** no line written by the service contains that token

#### Scenario: Body with personal data

- **WHEN** a request carries a JSON body with a name and an email address
- **THEN** no line written by the service contains that name or that email address

#### Scenario: Cookie header

- **WHEN** a request carries a `Cookie` header
- **THEN** no line written by the service contains its value

### Requirement: Logging never changes the response

Writing the request log line MUST NOT change the status, headers or body of the response, and a failure while
writing the line MUST NOT turn a response into an error.

#### Scenario: Response unchanged by the log

- **WHEN** a client sends `GET /api/catalog/health` with and without the request log middleware enabled
- **THEN** the status, body and headers set by the service are the same

#### Scenario: Log write fails

- **WHEN** writing the request log line raises an error
- **THEN** the client still gets the response of the endpoint unchanged

### Requirement: The server writes no other access log

The services SHALL NOT write the default access line of the application server, so each request appears once in
the service log.

#### Scenario: One line per request

- **WHEN** a client sends one request to a service
- **THEN** the service log has one line for that request, the request log line, and no Uvicorn access line
