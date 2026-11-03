# Spec Delta

## Purpose

Provisions the project's identity configuration automatically, so every environment starts with the `ticketera`
realm and the roles `ADMIN`, `EVENT_OWNER` and `CLIENT` without manual setup, and without secrets in the
repository.

## ADDED Requirements

### Requirement: The ticketera realm is imported on startup

The identity service SHALL import the `ticketera` realm from its definition in the repository when it starts
without that realm.

#### Scenario: First start

- **WHEN** the identity service starts for the first time
- **THEN** the `ticketera` realm exists and is enabled

#### Scenario: Start after removing all data

- **WHEN** a team member runs `docker compose down -v` and then `docker compose up`
- **THEN** the identity service imports the `ticketera` realm again

### Requirement: An existing realm is not overwritten on restart

When the `ticketera` realm already exists, the identity service SHALL start without importing it again and
SHALL keep its current configuration.

#### Scenario: Restart with an existing realm

- **WHEN** the identity service restarts and the `ticketera` realm already exists
- **THEN** the identity service starts without errors and the realm keeps its current configuration

### Requirement: The realm contains the platform roles

The `ticketera` realm SHALL contain the realm roles `ADMIN`, `EVENT_OWNER` and `CLIENT`, and no other realm
role defined by the project.

#### Scenario: Roles of the imported realm

- **WHEN** a team member lists the realm roles of `ticketera` after the first start
- **THEN** the list contains `ADMIN`, `EVENT_OWNER` and `CLIENT`

#### Scenario: No other project roles

- **WHEN** a team member compares the realm roles of `ticketera` with those the identity service creates by
  default
- **THEN** the only roles added by the project are `ADMIN`, `EVENT_OWNER` and `CLIENT`

### Requirement: The realm definition contains no secrets

The realm definition stored in the repository MUST NOT contain passwords, client secrets or private keys.

#### Scenario: Reviewer reads the realm definition

- **WHEN** a reviewer reads the realm definition in the repository
- **THEN** it contains no password, client secret or private key

### Requirement: Administrator credentials come from local configuration

The identity service SHALL create its administrator account from credentials in the local configuration, never
from values stored in the repository.

#### Scenario: Administrator signs in to the admin console

- **WHEN** a team member signs in to the admin console with the administrator credentials
- **THEN** the sign-in succeeds with the credentials that were set in `.env` when the identity service first
  started

#### Scenario: Administrator credentials missing

- **WHEN** the administrator credentials are missing from `.env`
- **THEN** startup stops before any container starts and the error names the missing value

### Requirement: The identity service is healthy only after the realm is available

The identity service SHALL report a healthy status only when the `ticketera` realm is available.

#### Scenario: Identity service reports healthy

- **WHEN** the identity service reports a healthy status
- **THEN** the discovery document of the `ticketera` realm answers `200 OK`
