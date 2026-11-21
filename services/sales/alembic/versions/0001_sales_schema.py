"""Create sales schema (seats, orders, tickets, idempotency_keys)

Revision ID: 0001_sales_schema
Revises: None
Create Date: 2026-11-21 10:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0001_sales_schema'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Seats table
    op.create_table(
        'seats',
        sa.Column('event_id', sa.String(), nullable=False),
        sa.Column('seat_id', sa.String(), nullable=False),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('price_centavos', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(length=3), server_default='ARS', nullable=False),
        sa.Column('status', sa.String(length=20), server_default='AVAILABLE', nullable=False),
        sa.PrimaryKeyConstraint('event_id', 'seat_id', name='pk_seats'),
    )

    # 2. Orders table
    op.create_table(
        'orders',
        sa.Column('order_id', sa.String(), nullable=False),
        sa.Column('customer_id', sa.String(), nullable=False),
        sa.Column('event_id', sa.String(), nullable=False),
        sa.Column('total_amount_centavos', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(length=3), server_default='ARS', nullable=False),
        sa.Column('status', sa.String(length=20), server_default='CONFIRMED', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('order_id', name='pk_orders'),
    )
    op.create_index('ix_orders_customer_id', 'orders', ['customer_id'])

    # 3. Tickets table
    op.create_table(
        'tickets',
        sa.Column('ticket_id', sa.String(), nullable=False),
        sa.Column('order_id', sa.String(), nullable=False),
        sa.Column('event_id', sa.String(), nullable=False),
        sa.Column('seat_id', sa.String(), nullable=False),
        sa.Column('ticket_code', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['orders.order_id'], name='fk_tickets_order_id'),
        sa.PrimaryKeyConstraint('ticket_id', name='pk_tickets'),
        sa.UniqueConstraint('event_id', 'seat_id', name='uq_tickets_event_seat'),
    )

    # 4. Idempotency keys table
    op.create_table(
        'idempotency_keys',
        sa.Column('customer_id', sa.String(), nullable=False),
        sa.Column('key', sa.String(), nullable=False),
        sa.Column('request_hash', sa.String(length=64), nullable=False),
        sa.Column('response_status', sa.Integer(), nullable=True),
        sa.Column('response_body', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('customer_id', 'key', name='pk_idempotency_keys'),
    )


def downgrade() -> None:
    op.drop_table('idempotency_keys')
    op.drop_table('tickets')
    op.drop_index('ix_orders_customer_id', table_name='orders')
    op.drop_table('orders')
    op.drop_table('seats')
