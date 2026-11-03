# Spec Delta

## Purpose

Lets any team member start the whole system on their own machine with a single command, with every container
reporting its health, starting in dependency order, exposed only to the local machine, running without root
privileges, and with no secrets in the repository.

## ADDED Requirements

### Requirement: A single command starts the whole system

Running `docker compose up` from the repository root, on a clean clone with `.env` copied from `.env.example`,
SHALL start every container of the system and bring all of them to a healthy state within 5 minutes, excluding
the first download and build of images.

#### Scenario: First start on a clean clone

- **WHEN** a team member clones the repository, copies `.env.example` to `.env` and runs `docker compose up`
  from the repository root
- **THEN** every container reaches a healthy state within 5 minutes after the images are built

#### Scenario: Restart with existing data

- **WHEN** the system was started before and a team member runs `docker compose up` again
- **THEN** every container reaches a healthy state and the data stored in the previous run is kept

#### Scenario: Start after removing all data

- **WHEN** a team member runs `docker compose down -v` and then `docker compose up`
- **THEN** the system starts with empty databases, creates the database of each service again and every
  container reaches a healthy state

### Requirement: Every container reports its health

Every container of the system SHALL report a health status that is healthy only while it can serve its function,
and SHALL report unhealthy within 60 seconds after it stops responding.

#### Scenario: All containers healthy

- **WHEN** the system has started
- **THEN** every container reports a healthy status

#### Scenario: A service stops responding

- **WHEN** a running backend service stops responding to requests
- **THEN** its container reports an unhealthy status within 60 seconds

### Requirement: Containers wait for their dependencies to be healthy

A container SHALL start only after every container it depends on reports a healthy status.

#### Scenario: Database not yet healthy

- **WHEN** the system starts and the database container is not yet healthy
- **THEN** the backend services and the identity service wait and start only after the database is healthy

#### Scenario: A dependency never becomes healthy

- **WHEN** a team member runs `docker compose up --wait` and the database never reaches a healthy state
- **THEN** the command fails and reports the database container as unhealthy

### Requirement: Only the gateway and the frontend publish ports

The gateway and the frontend SHALL be the only containers that publish ports to the host; the database, the
identity service and the backend services MUST publish none.

#### Scenario: Published ports of a running system

- **WHEN** a team member lists the ports published by the running system
- **THEN** only the gateway and the frontend have published ports

#### Scenario: Connection from the host to the database or the identity service

- **WHEN** a team member connects from the host to the port of the database or of the identity service
- **THEN** no container of the system accepts the connection

### Requirement: Published ports are reachable only from the local machine

The ports published by the gateway and the frontend SHALL accept connections only from the local machine.

#### Scenario: Connection from the local machine

- **WHEN** a team member opens the frontend or the gateway in a browser on the same machine
- **THEN** the page or response is served

#### Scenario: Connection from another machine on the network

- **WHEN** another machine on the same network connects to the published port of the gateway or the frontend
- **THEN** the connection is refused

### Requirement: Secrets are kept out of the repository

The repository MUST NOT contain secrets: local configuration lives in `.env`, which is never tracked, and
`.env.example` contains only non-secret placeholder values.

#### Scenario: Local configuration file is not tracked

- **WHEN** a team member creates `.env` from `.env.example`
- **THEN** Git does not list `.env` as a file to commit

#### Scenario: Example configuration holds placeholders only

- **WHEN** a reviewer reads `.env.example`
- **THEN** every credential in it is a placeholder value, not a real secret

### Requirement: Missing configuration stops startup with a clear error

The system SHALL refuse to start when a required configuration value is missing, before starting any container,
and SHALL name the missing value in the error.

#### Scenario: Missing local configuration file

- **WHEN** a team member runs `docker compose up` without creating `.env`
- **THEN** startup stops before any container starts and the error names a missing required value

#### Scenario: Required value left empty

- **WHEN** `.env` exists but a required database password is empty
- **THEN** startup stops before any container starts and the error names that value

### Requirement: Project commands run inside containers

Every project command (dependency installation, lint, type check, tests, migrations) SHALL run inside the
containers through `docker compose`, so the host needs no project runtime or project dependency.

#### Scenario: Tests on a host without project runtimes or dependencies

- **WHEN** a team member whose host has no Python and none of the project dependencies installed runs the tests
  of a service through `docker compose`
- **THEN** the tests run inside the service's container and report their result

### Requirement: Containers run as a non-root user

The containers built by the project SHALL run their processes as a non-root user.

#### Scenario: Process user of a project container

- **WHEN** a team member checks the user that runs the main process of a container built by the project
- **THEN** the user is not root

### Requirement: Files created in mounted folders belong to the host user

Files that project commands create in a mounted source folder SHALL be owned by the host user who runs the
system.

#### Scenario: File generated by the tests

- **WHEN** the tests of a service generate a file in its mounted source folder
- **THEN** the host user can edit and delete that file without `sudo`

### Requirement: Source changes are reflected without rebuilding

The source folder of each service SHALL be mounted into its container, so a change saved on the host is served
by the running container within 10 seconds, without rebuilding the image.

#### Scenario: Change to a backend service

- **WHEN** a team member saves a change to a source file under `services/catalog/` while the system runs
- **THEN** the running `catalog` service serves the change within 10 seconds without an image rebuild

#### Scenario: Change to the frontend

- **WHEN** a team member saves a change to a source file under `frontend/` while the system runs
- **THEN** the frontend serves the change within 10 seconds without an image rebuild
