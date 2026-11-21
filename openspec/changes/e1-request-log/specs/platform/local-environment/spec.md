# Spec Delta

## MODIFIED Requirements

### Requirement: Only the gateway and the frontend publish ports

The gateway, the frontend and Grafana SHALL be the only containers that publish ports to the host; the database,
the identity service, the backend services, Loki and the log collector MUST publish none.

#### Scenario: Published ports of a running system

- **WHEN** a team member lists the ports published by the running system
- **THEN** only the gateway, the frontend and Grafana have published ports

#### Scenario: Connection from the host to the database or the identity service

- **WHEN** a team member connects from the host to the port of the database or of the identity service
- **THEN** no container of the system accepts the connection

#### Scenario: Connection from the host to Loki

- **WHEN** a team member connects from the host to the Loki port
- **THEN** no container of the system accepts the connection

### Requirement: Published ports are reachable only from the local machine

The ports published by the gateway, the frontend and Grafana SHALL accept connections only from the local
machine.

#### Scenario: Connection from the local machine

- **WHEN** a team member opens the frontend, the gateway or Grafana in a browser on the same machine
- **THEN** the page or response is served

#### Scenario: Connection from another machine on the network

- **WHEN** another machine on the same network connects to the published port of the gateway, the frontend or
  Grafana
- **THEN** the connection is refused
