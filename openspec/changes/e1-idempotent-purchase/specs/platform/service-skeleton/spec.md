# Spec Delta

## Purpose

Establishes the reference hexagonal architecture structure, layer linting rules, and Alembic migration conventions
(D-33) that all backend microservices follow.

## ADDED Requirements

### Requirement: Four-layer hexagonal directory structure

Every backend service SHALL organize its source code into four distinct layers under `src/<service>/`:
`domain/`, `application/`, `infrastructure/`, and `api/`.

#### Scenario: Domain layer purity

- **WHEN** inspecting `services/<service>/src/<service>/domain/`
- **THEN** source files import only standard Python library modules, containing zero imports from FastAPI,
  SQLAlchemy, Pydantic, or other framework dependencies

#### Scenario: Inward dependency direction

- **WHEN** analyzing imports across layers
- **THEN** `domain/` imports nothing outside domain; `application/` imports only from `domain/`; `infrastructure/`
  and `api/` import from `application/` and `domain/`, but neither `domain/` nor `application/` imports from
  `infrastructure/` or `api/`

### Requirement: Architectural layer linting with import-linter

The project's CI `quality` job SHALL run an `import-linter` contract verifying that layer boundaries and inward
dependency directions are strictly preserved across all services.

#### Scenario: Illegal outward import rejected by CI

- **WHEN** a file in `sales/domain/` imports from `sales/application/` or `sales/infrastructure/`
- **THEN** `import-linter` fails with a non-zero exit code during the `quality` check

### Requirement: Database schema migrations with Alembic

Each service with a relational database SHALL maintain an `alembic/` migration directory at the service root, with
versioned migration scripts that can upgrade and downgrade the schema.

#### Scenario: Running migrations from a clean database

- **WHEN** a service container starts against an empty database and runs `alembic upgrade head`
- **THEN** all required tables, constraints, and indexes are created successfully without manual SQL scripts

### Requirement: Separation of API schemas from domain entities

The `api/` layer SHALL use Pydantic models strictly for request validation and response serialization, never using
domain entities directly as HTTP request or response bodies.

#### Scenario: API request schema decoupled from domain entity

- **WHEN** an HTTP request is received by a FastAPI endpoint
- **THEN** the request payload is validated by a Pydantic schema and transformed into a domain entity or command
  DTO before passing it to the application use case
