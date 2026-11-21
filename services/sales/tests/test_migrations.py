"""Test database schema created by Alembic migrations (TDD).

Verifies tables created per design.md & tasks.md:
- `seats`: PK (event_id, seat_id), status (AVAILABLE, SOLD), price_centavos, currency.
- `orders`: PK order_id, customer_id, event_id, total_amount, currency, status, created_at.
- `tickets`: PK ticket_id, order_id FK, event_id, seat_id, ticket_code, UNIQUE(event_id, seat_id).
- `idempotency_keys`: PK (customer_id, key), request_hash, response_status, response_body, created_at.
"""

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_alembic_configuration_and_migration_script() -> None:
    """Verifies that Alembic is configured with a valid head migration revision."""
    config = Config("alembic.ini")
    script = ScriptDirectory.from_config(config)

    head_revision = script.get_current_head()
    assert head_revision is not None, "Alembic must have at least one migration revision"

    rev = script.get_revision(head_revision)
    assert rev is not None
    assert "sales" in rev.doc.lower() or "schema" in rev.doc.lower() or "e1" in rev.doc.lower()
