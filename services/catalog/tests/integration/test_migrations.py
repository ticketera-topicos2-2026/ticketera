"""Tests of the catalog schema migrations (change e1-event-catalog, task 3.1; design EC-08, Persistence)."""

from alembic import command
from sqlalchemy import Engine, inspect

from tests.integration.conftest import alembic_config

EXPECTED_TABLES = {"events", "event_zones", "event_participants", "idempotency_keys"}


def test_upgrade_creates_the_catalog_tables_and_downgrade_removes_them(engine: Engine) -> None:
    """Design EC-08: `alembic upgrade head` on an empty database creates the four tables; `downgrade base`
    removes them."""
    command.downgrade(alembic_config(), "base")
    assert EXPECTED_TABLES.isdisjoint(inspect(engine).get_table_names())

    command.upgrade(alembic_config(), "head")
    assert set(inspect(engine).get_table_names()) >= EXPECTED_TABLES


def test_schema_keeps_its_keys_checks_and_indexes(engine: Engine) -> None:
    """Design EC-08: primary keys, the state and modality checks, and the indexes of the public list, the
    owner's list and the participant search (DF-06)."""
    command.upgrade(alembic_config(), "head")
    inspector = inspect(engine)

    assert inspector.get_pk_constraint("event_zones")["constrained_columns"] == ["event_id", "code"]
    assert inspector.get_pk_constraint("idempotency_keys")["constrained_columns"] == ["owner_id", "key"]
    checks = {check["name"] for check in inspector.get_check_constraints("events")}
    checks |= {check["name"] for check in inspector.get_check_constraints("event_zones")}
    assert {"ck_events_status", "ck_event_zones_modality"} <= checks
    indexes = {index["name"] for index in inspector.get_indexes("events")}
    assert {"ix_events_status_starts_at", "ix_events_type_starts_at", "ix_events_owner_created_at"} <= indexes
    participant_indexes = {index["name"] for index in inspector.get_indexes("event_participants")}
    assert "ix_event_participants_name" in participant_indexes
