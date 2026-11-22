"""Catalog schema: events, zones, participants and idempotency keys (change e1-event-catalog; design EC-08).

Revision ID: 0001_catalog_schema
Revises:
Create Date: 2026-11-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_catalog_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.String(5000), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("organizer_name", sa.String(200), nullable=False),
        sa.Column("venue_name", sa.String(200), nullable=False),
        sa.Column("venue_city", sa.String(200), nullable=False),
        sa.Column("venue_address", sa.String(300), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('DRAFT', 'PUBLISHED')", name="ck_events_status"),
        sa.CheckConstraint("version >= 1", name="ck_events_version"),
    )
    op.create_index("ix_events_status_starts_at", "events", ["status", "starts_at"])
    op.create_index("ix_events_type_starts_at", "events", ["type", "starts_at"])
    op.create_index("ix_events_owner_created_at", "events", ["owner_id", sa.text("created_at DESC")])

    op.create_table(
        "event_zones",
        sa.Column("event_id", sa.Uuid(), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(8), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("modality", sa.String(20), nullable=False),
        sa.Column("seat_count", sa.Integer(), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("event_id", "code"),
        sa.CheckConstraint(
            "(modality = 'NUMBERED' AND seat_count IS NOT NULL AND capacity IS NULL)"
            " OR (modality = 'UNNUMBERED' AND capacity IS NOT NULL AND seat_count IS NULL)",
            name="ck_event_zones_modality",
        ),
    )

    op.create_table(
        "event_participants",
        sa.Column("event_id", sa.Uuid(), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.PrimaryKeyConstraint("event_id", "position"),
    )
    # Ready for the search by participant of Stage III (DF-06).
    op.create_index("ix_event_participants_name", "event_participants", [sa.text("lower(name)")])

    op.create_table(
        "idempotency_keys",
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("key", sa.Uuid(), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("owner_id", "key"),
    )


def downgrade() -> None:
    op.drop_table("idempotency_keys")
    op.drop_index("ix_event_participants_name", table_name="event_participants")
    op.drop_table("event_participants")
    op.drop_table("event_zones")
    op.drop_index("ix_events_owner_created_at", table_name="events")
    op.drop_index("ix_events_type_starts_at", table_name="events")
    op.drop_index("ix_events_status_starts_at", table_name="events")
    op.drop_table("events")
