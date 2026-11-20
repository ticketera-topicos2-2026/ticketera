# Spec Delta

## ADDED Requirements

### Requirement: The gateway gives every request a correlation id

The gateway SHALL generate a new correlation id for every request it receives, made of 32 lowercase hexadecimal
characters, and SHALL return it to the client in the `X-Correlation-ID` response header, whatever the status
code, including the requests it answers by itself.

#### Scenario: Forwarded request

- **WHEN** a client sends `GET /api/catalog/health` to the gateway
- **THEN** the response carries an `X-Correlation-ID` header of 32 lowercase hexadecimal characters

#### Scenario: Request rejected by the access check

- **WHEN** a client sends `GET /api/sales/example` without a token
- **THEN** the gateway answers `401 Unauthorized` with an `X-Correlation-ID` header

#### Scenario: Path that matches no route

- **WHEN** a client sends `GET /api/unknown/example`
- **THEN** the gateway answers `404 Not Found` with an `X-Correlation-ID` header

#### Scenario: Service stopped

- **WHEN** the `payments` service is stopped and a client sends `GET /api/payments/health`
- **THEN** the gateway answers `502 Bad Gateway` with an `X-Correlation-ID` header

#### Scenario: Two consecutive requests

- **WHEN** a client sends the same request to the gateway twice
- **THEN** the two responses carry different correlation ids

#### Scenario: Concurrent requests

- **WHEN** 50 clients send requests to the gateway at the same time
- **THEN** the 50 responses carry 50 different correlation ids

### Requirement: The correlation id is never taken from the client

The gateway MUST NOT use, forward or return a correlation id sent by the client; a client value in
`X-Correlation-ID` SHALL be replaced by the one the gateway generates.

#### Scenario: Client sends its own correlation id

- **WHEN** a client sends `GET /api/catalog/health` with the header `X-Correlation-ID: 00000000000000000000000000000000`
- **THEN** the response carries a different correlation id, and the `catalog` service receives and logs the
  gateway's id, not the client's

#### Scenario: Client sends a malicious correlation id

- **WHEN** a client sends a request with an `X-Correlation-ID` header that contains a quote, a line break or
  more than 32 characters
- **THEN** that value appears in no line of the gateway or service logs

### Requirement: The gateway forwards the correlation id to the service

The gateway SHALL send the correlation id of the request to the service it forwards the request to, in the
`X-Correlation-ID` request header, with the same value it returns to the client.

#### Scenario: Correlation id seen by the service

- **WHEN** a client sends `GET /api/sales/health` through the gateway
- **THEN** the `sales` service receives an `X-Correlation-ID` header equal to the one in the client's response

#### Scenario: Request to the identity service

- **WHEN** a client sends `GET /auth/realms/ticketera/.well-known/openid-configuration` through the gateway
- **THEN** the identity service receives an `X-Correlation-ID` header equal to the one in the client's response

### Requirement: The same correlation id ties the gateway line to the service line

For every request the gateway forwards to a backend service, the gateway log line and the service log line of
that request SHALL carry the same correlation id.

#### Scenario: Request followed from the gateway to the service

- **WHEN** a client sends `GET /api/catalog/health` and reads the correlation id of the response
- **THEN** exactly one gateway log line and exactly one `catalog` log line carry that correlation id, and both
  record status `200`

### Requirement: Services accept only a well-formed correlation id

A backend service SHALL log the value of the `X-Correlation-ID` request header only when it is exactly 32
lowercase hexadecimal characters, and SHALL log a `null` correlation id otherwise, including when the header is
missing.

#### Scenario: Request without the header

- **WHEN** the container healthcheck sends `GET /health` directly to the `catalog` service, without the header
- **THEN** the service answers normally and logs the request with a `null` correlation id

#### Scenario: Malformed header reaching a service

- **WHEN** a request reaches a service with `X-Correlation-ID: abc"}\n{"status":200`
- **THEN** the service logs the request with a `null` correlation id, and no line contains that value
