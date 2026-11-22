# Spec Delta

## ADDED Requirements

### Requirement: An EVENT_OWNER or an ADMIN creates a draft event

The `catalog` service SHALL let a user holding the `EVENT_OWNER` or the `ADMIN` role create an event with
`POST /manage/events`, and SHALL answer `201 Created` with the new event in state `DRAFT`, a new identifier, version
`1` and the creator's `sub` as its owner. It SHALL answer `403 Forbidden` to any other user, without creating the
event.

#### Scenario: EVENT_OWNER creates a draft

- **WHEN** the `EVENT_OWNER` test user sends a valid event to `POST /api/catalog/manage/events` with an
  `Idempotency-Key`
- **THEN** the service answers `201 Created` with the event in state `DRAFT`, version `1`, a UUID identifier and
  that user's `sub` as owner

#### Scenario: ADMIN creates a draft

- **WHEN** the `ADMIN` test user sends a valid event to `POST /api/catalog/manage/events`
- **THEN** the service answers `201 Created` and the `ADMIN` is the owner of the draft

#### Scenario: CLIENT tries to create an event

- **WHEN** the `CLIENT` test user sends a valid event to `POST /api/catalog/manage/events`
- **THEN** the service answers `403 Forbidden` and no event is created

### Requirement: Event data is validated

An event SHALL have a title (1 to 200 characters), a description (up to 5000), a type (`CONCERT`, `THEATER`,
`SPORTS`, `CONFERENCE`, `FESTIVAL` or `OTHER`), an organizer name (1 to 200), up to 50 participants named with 1
to 200 characters, a start with a time zone offset, a venue with a name and a city, and up to 20 zones. The service
SHALL answer `422` to a request that breaks a rule, naming every offending field, and SHALL store nothing.

#### Scenario: Missing title and unknown type

- **WHEN** the `EVENT_OWNER` test user creates an event without a title and with the type `PARTY`
- **THEN** the service answers `422` naming `title` and `type`, and no event is created

#### Scenario: Start time without a time zone

- **WHEN** the `EVENT_OWNER` test user creates an event whose start is `2026-12-20T21:00:00`
- **THEN** the service answers `422` naming `starts_at`

#### Scenario: Too many participants

- **WHEN** the `EVENT_OWNER` test user creates an event with 51 participants
- **THEN** the service answers `422` naming `participants`

### Requirement: Fields outside the contract are rejected

The service SHALL answer `422` to a request to the management API that sends a field the contract does not define,
including the owner, the state, the publication time and the version on create, naming each such field, and SHALL
store nothing.

#### Scenario: Client tries to set the owner or the state

- **WHEN** the `EVENT_OWNER` test user creates an event whose body includes `owner_id` or `status: PUBLISHED`
- **THEN** the service answers `422` naming those fields, and no event is created

### Requirement: Each zone has a ticket modality

Each zone of an event SHALL have a code matching `^[A-Z0-9]{1,8}$`, unique within the event, a name, and a
ticket modality:

- `NUMBERED`, with a seat count from 1 to 5000 and no capacity. Its seats are identified as `<zone code>-<n>`, for
  `n` from 1 to the seat count.
- `UNNUMBERED`, with a capacity from 1 to 50000 and no seat count.

#### Scenario: Numbered zone

- **WHEN** an event has the zone `{code: "PLATEA", modality: "NUMBERED", seat_count: 3}`
- **THEN** the event shows that zone with the seat ids `PLATEA-1`, `PLATEA-2` and `PLATEA-3`

#### Scenario: Unnumbered zone

- **WHEN** an event has the zone `{code: "CAMPO", modality: "UNNUMBERED", capacity: 8000}`
- **THEN** the event shows that zone with its capacity and no seat ids

#### Scenario: Numbered zone with a capacity

- **WHEN** the `EVENT_OWNER` test user creates an event with a `NUMBERED` zone that has a capacity and no seat
  count
- **THEN** the service answers `422` naming the zone

#### Scenario: Repeated zone code

- **WHEN** the `EVENT_OWNER` test user creates an event with two zones whose code is `A`
- **THEN** the service answers `422` naming the repeated code

### Requirement: Event creation is idempotent

`POST /manage/events` SHALL require an `Idempotency-Key` header holding a UUID, and SHALL store the key, scoped to
the user's `sub`, in the same transaction as the event. A repeated request with the same key and the same body
SHALL get the original response without creating another event. The same key with a different body SHALL be
rejected.

#### Scenario: Missing key

- **WHEN** the `EVENT_OWNER` test user creates an event without an `Idempotency-Key`
- **THEN** the service answers `400 Bad Request` and no event is created

#### Scenario: Retry after a network timeout

- **WHEN** the `EVENT_OWNER` test user sends the same creation request twice with the same key
- **THEN** both responses are `201 Created` with the same event identifier, and only one event exists

#### Scenario: Same key with a different body

- **WHEN** the `EVENT_OWNER` test user reuses a key with a different title
- **THEN** the service answers `422` and no second event is created

#### Scenario: Two users with the same key

- **WHEN** the `EVENT_OWNER` and the `ADMIN` test users each create an event with the same key
- **THEN** two events are created, one owned by each user

#### Scenario: Concurrent requests with the same key

- **WHEN** the `EVENT_OWNER` test user sends the same creation request 10 times at the same time with the same
  key
- **THEN** exactly one event is created and every response carries its identifier

### Requirement: A draft is edited with its current version

The owner of a draft, or an `ADMIN`, SHALL replace its data with `PUT /manage/events/{event_id}`, sending the
version they read. The service SHALL answer `200 OK` with the version incremented by one when that version is
current, and `409 Conflict` without changes when it is not. A published event SHALL NOT be edited.

#### Scenario: Edit with the current version

- **WHEN** the owner sends `PUT` for a draft at version `1` with `version: 1` and a new title
- **THEN** the service answers `200 OK` with the new title and version `2`

#### Scenario: Edit with a stale version

- **WHEN** the owner sends `PUT` with `version: 1` for a draft that is at version `2`
- **THEN** the service answers `409 Conflict` and the draft is unchanged

#### Scenario: Two concurrent edits of the same version

- **WHEN** the owner and an `ADMIN` send `PUT` for the same draft at the same time, both with its current version
- **THEN** exactly one gets `200 OK`, the other gets `409 Conflict`, and the draft holds the data of the first

#### Scenario: Edit of a published event

- **WHEN** the owner sends `PUT` for a published event
- **THEN** the service answers `409 Conflict` and the event is unchanged

### Requirement: A draft is published once it is complete

The owner of a draft, or an `ADMIN`, SHALL publish it with `POST /manage/events/{event_id}/publish`. The service
SHALL publish it only when it has at least one zone and starts in the future, and SHALL then answer `200 OK` with
the event in state `PUBLISHED` and its publication time. Publishing an event that is already published SHALL
answer `200 OK` without changing it.

#### Scenario: Complete draft published

- **WHEN** the owner publishes a draft with two zones that starts next month
- **THEN** the service answers `200 OK` with state `PUBLISHED`, and the event appears in the public catalog

#### Scenario: Draft without zones

- **WHEN** the owner publishes a draft with no zones
- **THEN** the service answers `422` saying that a zone is required, and the event stays in `DRAFT`

#### Scenario: Draft that starts in the past

- **WHEN** the owner publishes a draft whose start time has passed
- **THEN** the service answers `422` naming `starts_at`, and the event stays in `DRAFT`

#### Scenario: Publishing twice

- **WHEN** the owner publishes an event that is already published
- **THEN** the service answers `200 OK` with the same publication time as the first time

#### Scenario: Publish and edit at the same time

- **WHEN** the owner publishes a draft while an `ADMIN` sends an edit of the same draft with its current version
- **THEN** either the edit is applied and then the event is published, or the event is published and the edit
  gets `409 Conflict`; no edit is ever applied to a published event

### Requirement: An EVENT_OWNER manages only their own events

An `EVENT_OWNER` SHALL read, edit and publish only the events they own, and the service SHALL answer
`404 Not Found` to any of those requests on another user's event, the same answer as for an event that does not
exist. An `ADMIN` SHALL manage every event.

#### Scenario: EVENT_OWNER reads another owner's draft

- **WHEN** the `EVENT_OWNER` test user sends `GET /api/catalog/manage/events/{id}` for a draft owned by the
  `ADMIN` test user
- **THEN** the service answers `404 Not Found` with the same body as for an unknown identifier

#### Scenario: EVENT_OWNER publishes another owner's draft

- **WHEN** the `EVENT_OWNER` test user publishes a draft owned by another user
- **THEN** the service answers `404 Not Found` and the draft stays in `DRAFT`

#### Scenario: ADMIN edits an EVENT_OWNER's draft

- **WHEN** the `ADMIN` test user edits a draft owned by the `EVENT_OWNER` test user, with its current version
- **THEN** the service answers `200 OK` and the owner does not change

### Requirement: Managers list the events they can manage

`GET /manage/events` SHALL list, in both states and newest first, the events of the requesting `EVENT_OWNER`, or
every event for an `ADMIN`. It SHALL be paginated with `limit` (default 20, maximum 100) and `offset`.

#### Scenario: EVENT_OWNER lists their events

- **WHEN** the `EVENT_OWNER` test user, who owns one draft and one published event, lists their events
- **THEN** the response contains exactly those two events, and none owned by another user

#### Scenario: ADMIN lists every event

- **WHEN** the `ADMIN` test user lists the events
- **THEN** the response contains the events of every owner

#### Scenario: Limit above the maximum

- **WHEN** a manager lists events with `limit=500`
- **THEN** the service answers `422` naming `limit`
