# Spec Delta

## ADDED Requirements

### Requirement: The public catalog lists only published events

`GET /events` SHALL list the published events whose start time has not passed, ordered by start time, earliest
first, to any client, with or without a token. It SHALL never list a draft. Each item SHALL show the identifier,
title, type, organizer name, participants, start time, venue and zones of the event, and SHALL NOT show its owner.

#### Scenario: Visitor without a token

- **WHEN** a client without a token sends `GET /api/catalog/events` through the gateway
- **THEN** the response is `200 OK` with the published upcoming events, earliest first

#### Scenario: Draft not listed

- **WHEN** an `EVENT_OWNER` has a draft and a client lists the catalog
- **THEN** the draft is not in the response

#### Scenario: Owner not shown

- **WHEN** a client lists the catalog
- **THEN** no item of the response contains the `sub` of its owner

### Requirement: The public catalog is filtered and paginated

`GET /events` SHALL accept the filters `type`, `starts_from` and `starts_to` (date and time with a time zone
offset), combined with AND, and the pagination parameters `limit` (default 20, maximum 100) and `offset`. It SHALL
answer `422` to an invalid filter or pagination value.

#### Scenario: Filter by type and date range

- **WHEN** a client lists the catalog with `type=CONCERT`, `starts_from=2026-12-01T00:00:00-03:00` and
  `starts_to=2026-12-31T23:59:59-03:00`
- **THEN** the response contains only published concerts that start in December 2026

#### Scenario: Second page

- **WHEN** 25 published events exist and a client lists the catalog with `limit=10&offset=20`
- **THEN** the response contains the last 5 events in start order

#### Scenario: Invalid type

- **WHEN** a client lists the catalog with `type=PARTY`
- **THEN** the service answers `422` naming `type`

### Requirement: The public catalog shows a published event

`GET /events/{event_id}` SHALL show a published event, with its zones and, for each numbered zone, its seat ids.
It SHALL answer `404 Not Found` with the same body for a draft and for an identifier that does not exist.

#### Scenario: Published event

- **WHEN** a client requests a published event that has a numbered zone of 3 seats
- **THEN** the response is `200 OK` with the event and that zone's 3 seat ids

#### Scenario: Draft requested by its identifier

- **WHEN** a client requests a draft by its identifier through the public catalog
- **THEN** the service answers `404 Not Found` with the same body as for an unknown identifier

### Requirement: The public catalog ignores tokens

The public catalog endpoints SHALL answer the same way whether the request carries a token or not, valid,
tampered or expired, and SHALL NOT use a token to show a draft. They SHALL accept only `GET` and `HEAD`.

#### Scenario: Owner's token on the public endpoint

- **WHEN** the owner of a draft requests it through `GET /api/catalog/events/{id}` with a valid access token
- **THEN** the service answers `404 Not Found`, as for a client without a token

#### Scenario: Tampered token on a public path

- **WHEN** a client lists the catalog with a bearer token whose payload claims the `ADMIN` role and has been
  altered
- **THEN** the response is the same as without a token

#### Scenario: Write method on the public path

- **WHEN** a client sends `POST /api/catalog/events` with a valid `EVENT_OWNER` token
- **THEN** no event is created and the service answers `405 Method Not Allowed`

### Requirement: The public catalog answers quickly

On a development machine with every service healthy and 100 published events, the 95th percentile of the response
time of 100 sequential `GET /api/catalog/events?limit=100` requests through the gateway SHALL be 300 ms or less.

#### Scenario: Catalog latency measured on a development machine

- **WHEN** a team member sends 10 warm-up and then 100 sequential requests for the first 100 events of a catalog
  with 100 published events
- **THEN** the 95th percentile of the 100 response times is 300 ms or less
