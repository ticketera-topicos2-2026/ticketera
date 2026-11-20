# Spec Delta

## ADDED Requirements

### Requirement: The gateway writes one JSON access log line per request

The gateway SHALL write one access log line to standard output for every request it receives, including the
requests it answers by itself (`401`, `404`, `421`, CORS preflights) and those whose upstream fails (`502`),
except the requests to `/healthz`.

#### Scenario: Forwarded request

- **WHEN** a client sends `GET /api/catalog/health` through the gateway
- **THEN** the gateway writes exactly one access log line for it

#### Scenario: Request rejected by the access check

- **WHEN** a client sends `GET /api/sales/example` without a token
- **THEN** the gateway writes one line with status `401` and the `sales` service writes none

#### Scenario: Request to a stopped service

- **WHEN** the `payments` service is stopped and a client sends `GET /api/payments/health`
- **THEN** the gateway writes one line with status `502`

#### Scenario: Unexpected host name

- **WHEN** a client sends a request with the header `Host: attacker.example`
- **THEN** the gateway answers `421` and writes one line with status `421`

#### Scenario: Gateway healthcheck

- **WHEN** the container healthcheck requests `/healthz`
- **THEN** the gateway writes no access log line for it

### Requirement: The gateway access log line has a fixed set of fields

Each gateway access log line SHALL be a single JSON object with exactly these fields: `timestamp` (RFC 3339),
`service` (`gateway`), `correlation_id`, `method`, `path` (the normalized path, without the query string),
`status` (integer), `duration_seconds` (number) and `client_address`.

#### Scenario: Fields of a gateway line

- **WHEN** a client sends `GET /api/catalog/health` through the gateway
- **THEN** its line is valid JSON with exactly those fields, `service` `gateway`, `method` `GET`, `path`
  `/api/catalog/health`, `status` `200`, a numeric `duration_seconds` and the correlation id of the response

### Requirement: The gateway access log keeps tokens and the query string out

The gateway access log line MUST NOT contain the query string, the referrer, the `Authorization` or `Cookie`
headers, or any token, and MUST NOT contain any client-supplied header value other than the method and the
normalized path. Values SHALL be JSON-escaped so that no request can break a line or add a field.

#### Scenario: Query string with a token

- **WHEN** a client sends `GET /api/sales/example?access_token=<valid access token>`
- **THEN** the gateway line has `path` `/api/sales/example` and contains no part of the token

#### Scenario: Path with a quote and an encoded line break

- **WHEN** a client sends a request whose path contains `%22` and `%0A`
- **THEN** the gateway writes exactly one line for it, and that line is valid JSON with the same fixed fields
