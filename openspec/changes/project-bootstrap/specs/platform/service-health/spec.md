# Spec Delta

## Purpose

Gives every backend service a uniform health endpoint that reports the service's status and its database
connectivity, and gives the team a frontend status page that shows the health of every backend service through
the gateway.

## ADDED Requirements

### Requirement: The health endpoint reports a healthy service

Each backend service SHALL answer `GET /health` with `200 OK` and a JSON body containing `status` set to `ok`,
`service` set to its name and `database` set to `ok` when it can reach its database, within 1 second.

#### Scenario: Healthy catalog service

- **WHEN** a client sends `GET /api/catalog/health` to the gateway while the `catalog` service can reach its
  database
- **THEN** the response is `200 OK` within 1 second with `status` `ok`, `service` `catalog` and `database` `ok`

### Requirement: The health endpoint reports an unreachable database

When a backend service cannot reach its database, it SHALL answer `GET /health` with `503 Service Unavailable`
and a JSON body containing `status` set to `unavailable` and `database` set to `unavailable`, within 3 seconds.

#### Scenario: Database stopped

- **WHEN** the database container is stopped and a client sends `GET /api/sales/health` to the gateway
- **THEN** the response is `503 Service Unavailable` within 3 seconds with `status` `unavailable`, `service`
  `sales` and `database` `unavailable`

#### Scenario: Database available again

- **WHEN** the database container starts again after being stopped
- **THEN** the next `GET /health` of each backend service answers `200 OK` with `database` `ok`, without
  restarting the service

### Requirement: The health endpoint requires no authentication

The health endpoint of each backend service SHALL answer without requiring any credentials.

#### Scenario: Request without credentials

- **WHEN** a client with no credentials sends `GET /api/payments/health` to the gateway
- **THEN** the response is the health status of the `payments` service, not an authentication error

### Requirement: The health response reveals no internal details

The health response MUST NOT contain credentials, connection strings, internal host names, software versions,
error messages or stack traces, in any state.

#### Scenario: Healthy response content

- **WHEN** a client reads the health response of a healthy backend service
- **THEN** the body contains only `status`, `service` and `database`

#### Scenario: Response while the database is unavailable

- **WHEN** a client reads the health response of a backend service whose database is unavailable
- **THEN** the body contains only `status`, `service` and `database`, with no error message from the database

### Requirement: The health endpoint accepts only read requests

The health endpoint SHALL accept `GET` and `HEAD`, and SHALL answer `405 Method Not Allowed` to any other
method.

#### Scenario: HEAD request to the health endpoint

- **WHEN** a client sends `HEAD /api/catalog/health` to the gateway
- **THEN** the response has the same status code as `GET /api/catalog/health` and no body

#### Scenario: POST to the health endpoint

- **WHEN** a client sends `POST /api/catalog/health` to the gateway
- **THEN** the response is `405 Method Not Allowed`

### Requirement: The status page shows the health of every backend service

The frontend status page SHALL show each backend service (`catalog`, `sales`, `payments`) as healthy or
unhealthy, based on its health response through the gateway.

#### Scenario: All services healthy

- **WHEN** a team member opens the status page and every backend service answers `200 OK`
- **THEN** the page shows `catalog`, `sales` and `payments` as healthy

#### Scenario: One service unhealthy

- **WHEN** a team member opens the status page and the `sales` service answers `503 Service Unavailable`
- **THEN** the page shows `sales` as unhealthy and `catalog` and `payments` as healthy

#### Scenario: One service stopped

- **WHEN** the `payments` service is stopped and the gateway answers `502 Bad Gateway` for its route
- **THEN** the page shows `payments` as unhealthy and `catalog` and `sales` as healthy

### Requirement: Each health request of the status page has a time limit

Each health request made by the status page SHALL expire after 5 seconds; the service whose request expires
SHALL be shown as unhealthy, without affecting how the other services are shown.

#### Scenario: A health request expires

- **WHEN** the health request for `catalog` gets no answer within 5 seconds and `sales` and `payments` answer
  `200 OK`
- **THEN** the page shows `catalog` as unhealthy and `sales` and `payments` as healthy

### Requirement: The status page shows an unreachable gateway

When the gateway does not respond, the status page SHALL show every backend service as unhealthy and a message
that the gateway cannot be reached, instead of a blank or broken page.

#### Scenario: Gateway stopped

- **WHEN** the gateway is stopped and a team member opens the status page
- **THEN** the page shows every backend service as unhealthy and a message that the gateway cannot be reached
