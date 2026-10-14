# Spec Delta

## Purpose

Verifies every pull request to `main`, and every new commit on `main`, automatically and with least privilege,
inside the same containers the team uses, and reports the stable checks `openspec-validate`, `quality` and
`smoke-test` that protect `main`.

## ADDED Requirements

### Requirement: CI runs on every pull request to main

The CI SHALL run all its checks when a pull request to `main` is opened and again on every new push to its
branch.

#### Scenario: Pull request opened

- **WHEN** a team member opens a pull request to `main`
- **THEN** the checks `openspec-validate`, `quality` and `smoke-test` start on that pull request

#### Scenario: New push to the pull request

- **WHEN** a team member pushes a new commit to the branch of an open pull request to `main`
- **THEN** the three checks run again on the new commit

### Requirement: CI runs on every push to main

The CI SHALL run all its checks on every new commit that reaches `main`.

#### Scenario: Commit created by a squash merge

- **WHEN** a pull request is integrated into `main` with squash and merge
- **THEN** the checks `openspec-validate`, `quality` and `smoke-test` run on the new commit of `main`

### Requirement: Check names are stable

The CI SHALL report its results under exactly the names `openspec-validate`, `quality` and `smoke-test` on every
pull request to `main`, whatever files the pull request changes.

#### Scenario: Pull request that changes only documentation

- **WHEN** a pull request to `main` changes only files under `docs/`
- **THEN** the checks `openspec-validate`, `quality` and `smoke-test` are still reported on it

### Requirement: The openspec-validate check validates every OpenSpec artifact

The `openspec-validate` check SHALL fail when `openspec validate --all --strict` reports any error, and SHALL
pass otherwise.

#### Scenario: Invalid spec

- **WHEN** a pull request adds a requirement with no scenario
- **THEN** the `openspec-validate` check fails

#### Scenario: Valid artifacts

- **WHEN** every OpenSpec artifact in the pull request is valid
- **THEN** the `openspec-validate` check passes

### Requirement: The quality check builds, lints, type checks and tests every service

The `quality` check SHALL build the image of every service and run lint, type check and tests of every service
inside its container, and SHALL fail when any of these steps fails for any service, naming the service and the
step.

#### Scenario: Lint error in one service

- **WHEN** a pull request introduces a lint error in the `sales` service
- **THEN** the `quality` check fails and its output names the `sales` service and the lint step

#### Scenario: Failing test in the frontend

- **WHEN** a pull request introduces a failing test in the frontend
- **THEN** the `quality` check fails and its output names the frontend and the test step

#### Scenario: Image build fails

- **WHEN** a pull request breaks the image build of the `catalog` service
- **THEN** the `quality` check fails and its output names the `catalog` service and the build step

#### Scenario: Every step passes

- **WHEN** every service builds and passes lint, type check and tests
- **THEN** the `quality` check passes

### Requirement: The quality check rejects literal secrets in the realm definition

The `quality` check SHALL fail when a field of the realm definition that holds a secret, such as `secret`,
`privateKey` or `credentials`, contains a literal value; an environment variable placeholder such as
`${FRONT_CLIENT_SECRET}` SHALL pass.

#### Scenario: Realm definition with a literal client secret

- **WHEN** a pull request adds a client secret with a literal value to the realm definition
- **THEN** the `quality` check fails and its output names the field found

#### Scenario: Realm definition with a placeholder

- **WHEN** a pull request adds a client secret whose value is `${FRONT_CLIENT_SECRET}` to the realm definition
- **THEN** the realm secret verification of the `quality` check passes

### Requirement: The smoke-test check verifies the running system through the gateway

The `smoke-test` check SHALL start the system with the single startup command and verify through the gateway
that `/healthz`, the `ticketera` realm discovery document, `GET /api/<service>/health` of every backend service
and the frontend each answer `200 OK`.

#### Scenario: Every endpoint answers

- **WHEN** the system starts and every verified endpoint answers `200 OK` through the gateway
- **THEN** the `smoke-test` check passes

#### Scenario: A backend service is unhealthy

- **WHEN** `GET /api/sales/health` answers `503 Service Unavailable` during the smoke test
- **THEN** the `smoke-test` check fails and its output names the `sales` service

#### Scenario: The realm is missing

- **WHEN** the `ticketera` realm discovery document does not answer `200 OK` during the smoke test
- **THEN** the `smoke-test` check fails

### Requirement: The smoke test covers every backend service the system starts

The `smoke-test` check SHALL fail when the system starts a backend service whose health endpoint it does not
verify.

#### Scenario: Service added without smoke-test coverage

- **WHEN** a pull request adds a backend service to the system without adding it to the smoke test
- **THEN** the `smoke-test` check fails and its output names the uncovered service

### Requirement: The smoke test has a startup time limit

The `smoke-test` check SHALL fail when the system does not reach a healthy state within 5 minutes after the
images are built, and SHALL show the logs of every container that is not healthy.

#### Scenario: A container never becomes healthy

- **WHEN** the identity service does not reach a healthy state within 5 minutes during the smoke test
- **THEN** the `smoke-test` check fails and its output shows the logs of the identity service container

### Requirement: The smoke test leaves no state behind

After the smoke test, whether it passed or failed, the `smoke-test` check SHALL stop the system and remove its
containers and volumes.

#### Scenario: Cleanup after a failure

- **WHEN** the `smoke-test` check fails
- **THEN** the system is stopped and its containers and volumes are removed before the check ends

### Requirement: CI uses no repository secrets

The CI SHALL run every check with the configuration in `.env.example` and MUST NOT need repository secrets.

#### Scenario: Configuration used by the CI

- **WHEN** the CI runs on a pull request to `main`
- **THEN** it creates its configuration from `.env.example` and reads no repository secret

### Requirement: The workflow token is read-only

The token available to the CI SHALL have only read permissions on the repository.

#### Scenario: A check tries to push to the repository

- **WHEN** a step of a check tries to push a commit to the repository
- **THEN** the push is rejected and the check fails

### Requirement: Pull request code never runs with write permissions or secrets

The CI MUST NOT run code from a pull request with write permissions or with access to secrets, and its workflows
MUST NOT use the `pull_request_target` event.

#### Scenario: Pull request from a fork

- **WHEN** a pull request to `main` comes from a fork of the repository
- **THEN** its checks run with a read-only token and without access to any secret

### Requirement: The CI finishes within 15 minutes

All the checks of a pull request SHALL finish within 15 minutes on the hosted runners.

#### Scenario: Duration of the checks

- **WHEN** the CI runs on a pull request to `main` that changes every service
- **THEN** the checks `openspec-validate`, `quality` and `smoke-test` finish within 15 minutes
