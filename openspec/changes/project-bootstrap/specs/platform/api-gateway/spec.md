# Spec Delta

## Purpose

Makes the gateway the only entry point to the API: it routes each public path prefix to its service, serves the
identity service under `/auth`, forwards the original client information, lets the frontend call the API from
the browser, reports its own health, and never exposes the identity service's health and metrics endpoints.

## ADDED Requirements

### Requirement: The gateway is the only entry point to the API

Clients outside the system SHALL reach the backend services and the identity service only through the gateway.

#### Scenario: Request through the gateway

- **WHEN** a client on the local machine sends `GET /api/sales/health` to the gateway
- **THEN** the `sales` service answers it through the gateway

#### Scenario: Request to a service's internal address

- **WHEN** a client on the local machine sends a request to the internal address of the `sales` service
- **THEN** the request does not reach the `sales` service

### Requirement: The gateway serves only the expected host names

The gateway SHALL forward a request only when the host name in its `Host` header, regardless of the port, is one
of the host names used on the local machine (`localhost` or `127.0.0.1`), and SHALL answer
`421 Misdirected Request` to any other host name without forwarding the request.

#### Scenario: Request with an unexpected host name

- **WHEN** a client sends `GET /api/catalog/health` to the gateway with `Host: evil.example`
- **THEN** the gateway answers `421 Misdirected Request` and the `catalog` service does not receive the request

#### Scenario: Request with an expected host name

- **WHEN** a client sends `GET /api/catalog/health` to the gateway with `Host: localhost`
- **THEN** the request is forwarded to the `catalog` service

### Requirement: Each backend service has one route

The gateway SHALL forward every request under `/api/<service>/` to that backend service, with the
`/api/<service>` prefix removed and the status code and body of the response unchanged.

#### Scenario: Request routed to the catalog service

- **WHEN** a client sends `GET /api/catalog/health` to the gateway
- **THEN** the `catalog` service receives `GET /health` and the client gets its status code and body unchanged

#### Scenario: Request routed to the payments service

- **WHEN** a client sends `GET /api/payments/health` to the gateway
- **THEN** the `payments` service receives `GET /health`

### Requirement: Requests that match no route are rejected

The gateway SHALL answer `404 Not Found` to any request whose path matches no route, without forwarding it.

#### Scenario: Unknown backend service

- **WHEN** a client sends `GET /api/unknown/health` to the gateway
- **THEN** the gateway answers `404 Not Found`

#### Scenario: Path outside every route

- **WHEN** a client sends `GET /internal/status` to the gateway
- **THEN** the gateway answers `404 Not Found`

### Requirement: An unavailable service does not affect other routes

When a backend service does not respond, the gateway SHALL answer `502 Bad Gateway` for that service's route and
SHALL keep serving every other route.

#### Scenario: Catalog service stopped

- **WHEN** the `catalog` service is stopped and a client sends `GET /api/catalog/health`
- **THEN** the gateway answers `502 Bad Gateway`

#### Scenario: Other routes while one service is stopped

- **WHEN** the `catalog` service is stopped and a client sends `GET /api/sales/health`
- **THEN** the `sales` service answers it normally

### Requirement: The gateway forwards the original client information

The gateway SHALL send the original client address, host and scheme to the backend services and the identity
service, replacing any `X-Forwarded-For`, `X-Forwarded-Host` or `X-Forwarded-Proto` values sent by the client.

#### Scenario: Service receives the real client address

- **WHEN** a client sends `GET /api/catalog/health` to the gateway
- **THEN** the `catalog` service receives the client's real address as the client address

#### Scenario: Forged forwarding header

- **WHEN** a client sends a request to the gateway with a forged `X-Forwarded-For` header
- **THEN** the backend service still receives the client's real address and not the forged value

#### Scenario: Service receives the original host and scheme

- **WHEN** a client sends a request to the gateway with forged `X-Forwarded-Host` and `X-Forwarded-Proto` headers
- **THEN** the backend service receives the host and scheme the client actually used to reach the gateway

### Requirement: The frontend can call the API from the browser

The frontend, loaded in a browser from its own address, SHALL be able to call the API routes and receive their
responses without cross-origin errors; no other origin SHALL be granted cross-origin access.

#### Scenario: Status page loads the health of every service

- **WHEN** a team member opens the frontend status page in a browser on the local machine
- **THEN** the page receives the health response of every backend service with no cross-origin error in the
  browser

#### Scenario: CORS preflight from the frontend's address

- **WHEN** a browser sends a CORS preflight `OPTIONS /api/catalog/health` from the frontend's address
- **THEN** the preflight is answered successfully, the response allows the frontend's address as origin, and
  the `catalog` service does not receive the request

#### Scenario: CORS preflight from another origin

- **WHEN** a browser sends a CORS preflight `OPTIONS /api/catalog/health` from any address other than the
  frontend's
- **THEN** the response grants no permission to that origin: it neither allows every origin nor echoes the
  requested origin

### Requirement: The identity service is served under /auth

The gateway SHALL forward every request under `/auth/` to the identity service, including its admin console,
and the identity service SHALL publish URLs that start with the gateway's address followed by `/auth`.

#### Scenario: Discovery document of the ticketera realm

- **WHEN** a client sends `GET /auth/realms/ticketera/.well-known/openid-configuration` to the gateway
- **THEN** the response is `200 OK` and its issuer is the gateway's address followed by `/auth/realms/ticketera`

#### Scenario: Admin console from the local machine

- **WHEN** a team member opens `/auth/admin/` on the gateway from a browser on the local machine
- **THEN** the admin console of the identity service loads

### Requirement: Identity service health and metrics are never exposed

The gateway MUST NOT expose the health and metrics endpoints of the identity service.

#### Scenario: Identity service health through the gateway

- **WHEN** a client sends `GET /auth/health` or `GET /auth/health/ready` to the gateway
- **THEN** the gateway answers `404 Not Found`

#### Scenario: Identity service metrics through the gateway

- **WHEN** a client sends `GET /auth/metrics` to the gateway
- **THEN** the gateway answers `404 Not Found`

### Requirement: The gateway reports its own health

The gateway SHALL answer `GET /healthz` with `200 OK` by itself, without forwarding the request to any service.

#### Scenario: Gateway running

- **WHEN** a client sends `GET /healthz` to the gateway
- **THEN** the gateway answers `200 OK`

#### Scenario: Gateway health while a service is stopped

- **WHEN** the `catalog` service is stopped and a client sends `GET /healthz` to the gateway
- **THEN** the gateway still answers `200 OK`
