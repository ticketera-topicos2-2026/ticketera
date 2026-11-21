# Spec Delta

## ADDED Requirements

### Requirement: The logs of every container are collected and queryable

The local environment SHALL collect the standard output of every container of the system and make it queryable
in Grafana through a Loki data source, labeled with the Compose service name, without any change to the
containers that write it.

#### Scenario: Request found by its correlation id

- **WHEN** a client sends `GET /api/catalog/health` through the gateway and a team member queries Loki for the
  correlation id of the response
- **THEN** within 15 seconds the query returns the gateway line and the `catalog` line of that request

#### Scenario: Lines of one service

- **WHEN** a team member queries the lines labeled with the service `sales`
- **THEN** the result contains only lines written by the `sales` container

#### Scenario: Containers of another Compose project

- **WHEN** another Compose project runs on the same machine
- **THEN** none of its lines are collected

### Requirement: Grafana opens with the request log ready to use

Grafana SHALL start with a provisioned Loki data source and a provisioned dashboard that shows, for a chosen time
range, the number of requests per service, the number of requests per status code class, and the 50th, 95th and
99th percentiles of `duration_seconds` per service.

#### Scenario: First start

- **WHEN** a team member starts the system with `docker compose up` on a clean clone and signs in to Grafana
- **THEN** the Loki data source and the request log dashboard exist without any manual step

#### Scenario: Dashboard after some traffic

- **WHEN** a team member sends 20 requests to `/api/catalog/health` and opens the dashboard
- **THEN** the dashboard shows the `catalog` requests with status class `2xx`

### Requirement: Grafana requires the credentials from local configuration

Grafana SHALL accept only the administrator user and password set in `.env`, SHALL NOT allow anonymous access or
self sign-up, and `.env.example` SHALL hold only placeholder values for them. Startup SHALL stop with a clear
error when either value is missing.

#### Scenario: Anonymous visit

- **WHEN** a team member opens Grafana in a browser without signing in
- **THEN** Grafana shows its sign-in page and no dashboard or data

#### Scenario: Sign-in with the configured credentials

- **WHEN** a team member signs in with the user and password from `.env`
- **THEN** Grafana opens

#### Scenario: Missing password

- **WHEN** the Grafana administrator password is missing from `.env` and a team member runs `docker compose up`
- **THEN** the command stops before creating any container and names the missing variable

### Requirement: Log retention is bounded

Loki SHALL delete log lines older than 7 days, and its data SHALL be kept in a named volume that
`docker compose down -v` removes.

#### Scenario: Retention setting

- **WHEN** a team member reads the effective Loki configuration
- **THEN** retention is enabled with a period of 168 hours

#### Scenario: Clean reset

- **WHEN** a team member runs `docker compose down -v` and starts the system again
- **THEN** Loki holds no line from before the reset

### Requirement: Log collection does not affect the application

No application container (`database`, `identity`, `catalog`, `sales`, `payments`, `frontend`, `gateway`) SHALL
depend on the log collection containers, and stopping them SHALL NOT change any response of the system. Each log
collection container SHALL have a memory limit, and the three together SHALL be limited to 768 MiB or less.

#### Scenario: Log collection stopped

- **WHEN** a team member stops Loki, Alloy and Grafana while the system runs
- **THEN** every route of the gateway answers as before and every application container stays healthy

#### Scenario: Memory limits

- **WHEN** a team member inspects the running log collection containers
- **THEN** each one has a memory limit and the sum of the three limits is at most 768 MiB

### Requirement: The log collector has read-only access to the container runtime

The log collector SHALL read container logs through the Docker socket mounted read-only, SHALL publish no port,
and SHALL share a network only with Loki. It MAY run as root, which the socket requires, and SHALL then hold no
Linux capability; no other container of the system SHALL run as root.

#### Scenario: Collector mounts and networks

- **WHEN** a team member inspects the log collector container
- **THEN** the Docker socket is mounted read-only, no port is published, and its only network is the one it
  shares with Loki

#### Scenario: Collector runs as root without capabilities

- **WHEN** a team member checks the user and capabilities of the main process of every container
- **THEN** only the log collector runs as root, and it has every capability dropped
