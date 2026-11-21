# Proposal

> Builds on the token-claims contract of `e1-identity-access` (#30, merged) and on the four-layer service skeleton
> and the contract-test mechanism of `e1-idempotent-purchase` (D-33, D-24, #32). Implementation starts once the
> skeleton of #32 is merged.

## Why

The platform sells tickets for events, but no event exists anywhere: `catalog` is a skeleton with `/health`, and
`sales` loads its inventory against an `event_id` that nothing defines (D-28). An `EVENT_OWNER` cannot create an
event, and a `CLIENT` cannot browse what is on sale. PLAN 7.3 assigns the minimal event catalog to Stage I, and the
role table of PLAN 1.1 gives the `EVENT_OWNER` the job of designing, configuring and publishing events. DF-02
(numbered and unnumbered tickets) is a Stage I requirement without a change (PLAN 5.3), and DF-06 (search by type,
organizer, participant and date, Stage III) needs that data to exist from Stage I.

## What Changes

- **Event aggregate in `catalog`** (D-33 skeleton):
  - Fields: title, description, event type, organizer name, participants (those who perform, S-03), start date
    and time, and venue.
  - Zones, each with its ticket modality (DF-02): `NUMBERED`, with a seat count and deterministic seat ids
    (`<zone code>-<n>`), or `UNNUMBERED`, with a capacity.
  - Two states: `DRAFT` and `PUBLISHED`.
- **Management API** under `/api/catalog/manage/events`, protected by the gateway and authorized by role in the
  service:
  - An `EVENT_OWNER` creates drafts, edits them, publishes them and lists them, and only for their own events.
  - An `ADMIN` does the same on any event.
  - A `CLIENT` gets `403`; another owner's event answers `404` (OWASP API1, BOLA).
  - Creation requires an `Idempotency-Key`. Edits carry a `version` that rejects lost updates.
  - A published event can no longer be edited in Stage I.
- **Public catalog API** under `/api/catalog/events`:
  - Lists and shows only published events, with filters by type and date range, pagination, and order by start
    date.
  - It needs no token and ignores any token it receives, because the gateway does not validate tokens on public
    paths.
- **Gateway public paths:** `GET` and `HEAD` on `/api/catalog/events` and `/api/catalog/events/<id>` skip the
  access check, with a strict pattern (modifies `platform/api-gateway` of #30; reviewed by A).
- **Token-claims contract** of #30, copied as written and implemented in the `catalog` API layer. The
  authentication adapter stores the accepted `sub` in `request.state.user_id` for the request log (D-23, RL-06).
- **Contract-first:** `services/catalog/openapi.yaml`, checked against the schema that FastAPI generates by the
  contract test of D-24.
- **Persistence:** PostgreSQL tables and Alembic migrations in the `catalog` database (D-06, D-33), with indexes
  ready for the Stage III search (DF-06).
- **Tests:** unit tests of the aggregate; application tests with fakes; integration tests against PostgreSQL
  (idempotency, versions, concurrency); acceptance tests of the API; a Bruno collection in `tests/api/catalog/`
  (D-24).
- **Mockups** in `docs/mockups/catalog/`, and React screens with the GoPass identity (D-28, D-38): public catalog,
  event detail, "My events", the event form and publishing.

## Capabilities

### New Capabilities

- `catalog/event-management`: drafts, edits, publication, ownership, idempotency and concurrency of events.
- `catalog/event-browsing`: the public catalog of published events.
- `catalog/service-access`: the token-claims contract of `e1-identity-access`, applied to `catalog`.

### Modified Capabilities

- `platform/api-gateway`: the public catalog paths skip the access check.

## Non-goals

- Selling, prices, availability and reservations: they stay in `sales` (D-28). The catalog describes the offer;
  `sales` loads its own inventory, keyed by the catalog's `event_id`, and never reads the catalog database (D-06).
- Synchronization between `catalog` and `sales`: in Stage I an `ADMIN` loads the `sales` inventory using the seat
  ids of the catalog. The integration event `EventPublished` is documented in the design and is emitted from
  Stage II, with RabbitMQ.
- The selling rules of unnumbered tickets (zone capacity) in `sales`: this change only models the modality.
- Cancelled, sold-out and finished states, editing a published event, and deleting events: they wait for the
  Event Storming (PLAN 12).
- Search by relevance (DF-06, Stage III, D-21), images and seat-map drawings.

## Impact

- **Bounded contexts:** `catalog` (supporting). It also touches the platform (a gateway public path) and documents
  the reference that `sales` keeps (`event_id`).
- **Responsible:** Integrante B (PLAN 7.3). Review by Integrante C (PLAN 6.1). The gateway part is reviewed by
  Integrante A, who owns the platform.
- **Coordination:**
  - With A (#30): the public-path rule, and the GoPass base and sign-in that the screens build on (#30, group 2).
  - With C (#32): the skeleton, `import-linter` and the contract-test check that this change reuses, and the format
    of the seat ids for the `sales` inventory.
- **Glossary:** `docs/domain/glossary.md` does not exist yet (it follows the Event Storming). This change uses
  event, zone, seat, venue, participant and organizer as defined in the design, and the glossary adopts or
  corrects them.

## Risks and Rollback

- **The Event Storming changes the model** (states, editing rules): the specs keep Stage I minimal, and a later
  change adds states without breaking these contracts.
- **A token on a public path is trusted:** the public endpoints ignore the `Authorization` header, and drafts are
  only reachable through the protected management API; tests prove both.
- **The gateway pattern opens more than intended:** a strict pattern on the method and the raw URI, as in IA-03,
  with smoke checks for neighboring paths.
- **The catalog and the `sales` inventory drift apart in Stage I:** the seat ids are deterministic and documented,
  and `EventPublished` closes the gap in Stage II.
- **Rollback:** revert the pull requests and run `alembic downgrade base` on the `catalog` database; no other
  service reads it.
