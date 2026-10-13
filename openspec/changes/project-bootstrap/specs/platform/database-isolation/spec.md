# Spec Delta

## Purpose

Ensures that each service owns its data: one logical database and one database role per service, so no service
can read or change another service's data and no service holds administrative privileges on the database.

## ADDED Requirements

### Requirement: Each service has its own logical database

The database container SHALL hold one logical database for each service that stores data: `catalog`, `sales`,
`payments` and the identity service.

#### Scenario: Databases after the first start

- **WHEN** the system starts for the first time
- **THEN** the database container holds one logical database for `catalog`, `sales`, `payments` and the
  identity service

### Requirement: Each service connects with its own role

Each service SHALL connect to its database with its own database role and credentials, distinct from those of
every other service and from the database administrator, and that role SHALL be able to create and change
objects in its own database.

#### Scenario: Service connects to its own database

- **WHEN** the `catalog` service connects to the `catalog` database with its own role
- **THEN** the connection succeeds and the role can create a table in that database

#### Scenario: Services do not share credentials

- **WHEN** a reviewer compares the database credentials configured for each service
- **THEN** every service uses a different role, and no service uses the database administrator role

### Requirement: A service cannot access another service's database

A service database SHALL accept connections only from its own service role and from the database administrator
role.

#### Scenario: Role of one service connects to another service's database

- **WHEN** the role of the `catalog` service tries to connect to the `sales` database
- **THEN** the connection is rejected with a permission error

#### Scenario: Role of the identity service connects to a backend service's database

- **WHEN** the role of the identity service tries to connect to the `payments` database
- **THEN** the connection is rejected with a permission error

#### Scenario: Role with no explicit grant

- **WHEN** a database role created without any grant tries to connect to any service database
- **THEN** the connection is rejected with a permission error

### Requirement: A service role cannot grant access to its database

The role of a service MUST NOT be able to grant access to its database to any other role.

#### Scenario: Catalog role grants access to the sales role

- **WHEN** the role of the `catalog` service grants `CONNECT` on the `catalog` database to the role of the
  `sales` service
- **THEN** no privilege is granted and the role of the `sales` service still cannot connect to the `catalog`
  database

### Requirement: Service roles have no administrative privileges

The role of each service MUST NOT be able to create databases, create roles, install extensions or act as a
database administrator.

#### Scenario: Service role tries to create a database

- **WHEN** the role of the `sales` service tries to create a new database
- **THEN** the operation is rejected with a permission error

#### Scenario: Service role tries to create a role

- **WHEN** the role of the `sales` service tries to create a new database role
- **THEN** the operation is rejected with a permission error

#### Scenario: Service role tries to install a cross-database extension

- **WHEN** the role of the `sales` service tries to install `dblink` or `postgres_fdw` in its database
- **THEN** the operation is rejected with a permission error
