# Spec Delta

## MODIFIED Requirements

### Requirement: Public paths skip the access check

The gateway SHALL forward `GET` and `HEAD` requests to `/api/<service>/health`, to `/api/catalog/events` and to
`/api/catalog/events/<event id>`, where the event id is a UUID in lowercase, and every request under `/auth/`,
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

#### Scenario: Public catalog without a token

- **WHEN** a client sends `GET /api/catalog/events?type=CONCERT&limit=10` without a token
- **THEN** the `catalog` service answers it and the client gets its status code

#### Scenario: Public event without a token

- **WHEN** a client sends `GET /api/catalog/events/3f2a9c0d-4b5e-4f70-8192-a3b4c5d6e7f8` without a token
- **THEN** the `catalog` service answers it and the client gets its status code

#### Scenario: Management path without a token

- **WHEN** a client sends `GET /api/catalog/manage/events` without a token
- **THEN** the gateway answers `401 Unauthorized` and the `catalog` service does not receive the request

#### Scenario: Write method on the public catalog path

- **WHEN** a client sends `POST /api/catalog/events` without a token
- **THEN** the gateway answers `401 Unauthorized` and the `catalog` service does not receive the request

#### Scenario: Path that only starts like a public catalog path

- **WHEN** a client sends, without a token, `GET /api/catalog/events/` or
  `GET /api/catalog/events/3f2a9c0d-4b5e-4f70-8192-a3b4c5d6e7f8/zones` or `GET /api/catalog/events/not-a-uuid`
- **THEN** the gateway answers `401 Unauthorized`

#### Scenario: Public catalog path of another service

- **WHEN** a client sends `GET /api/sales/events` without a token
- **THEN** the gateway answers `401 Unauthorized`
