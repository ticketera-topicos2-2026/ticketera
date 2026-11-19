# Spec Delta

## Purpose

Defines the inventory management capability in `sales`, enabling `ADMIN` users to initialize seat inventory for
events and clients to query seat availability.

## ADDED Requirements

### Requirement: Initialize event seat inventory

The `sales` service SHALL provide an administrative endpoint to initialize seat inventory for an `event_id`,
recording each seat's identifier, section or category, base price, and an initial status of `AVAILABLE`.

#### Scenario: Admin loads seat inventory for an event

- **WHEN** an administrator posts a valid inventory payload with 100 seats for an event `evt-100` to
  `POST /api/sales/events/evt-100/inventory`
- **THEN** the response is `201 Created` and all 100 seats are stored with status `AVAILABLE`

#### Scenario: Duplicate inventory initialization rejected

- **WHEN** an administrator posts inventory for an `event_id` that already has initialized seats
- **THEN** the response is `409 Conflict` and existing inventory is preserved without changes

#### Scenario: Empty or invalid seat list

- **WHEN** an administrator posts an inventory payload with an empty seat list or negative prices
- **THEN** the response is `422 Unprocessable Entity` and no seats are stored

### Requirement: Query available inventory

The `sales` service SHALL allow clients to list all seats currently in `AVAILABLE` status for a given `event_id`.

#### Scenario: Query seats for an event with available seats

- **WHEN** a client sends `GET /api/sales/events/evt-100/seats?status=AVAILABLE`
- **THEN** the response is `200 OK` containing the list of available seats with their identifiers, categories,
  and prices

#### Scenario: Query seats for an event with no available seats

- **WHEN** all seats for an event are in `SOLD` or `RESERVED` status and a client queries available seats
- **THEN** the response is `200 OK` with an empty seat list

### Requirement: Autonomous inventory persistence

The `sales` service SHALL persist its inventory in `sales_db` using `event_id` strictly as an opaque reference,
without querying or joining tables from `catalog_db`.

#### Scenario: Sales operates when catalog is unavailable

- **WHEN** the `catalog` service is stopped or unreachable
- **THEN** `sales` continues to serve inventory queries and seat reservations for existing initialized events
  with `200 OK`
