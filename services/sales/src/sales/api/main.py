"""Composition root: wires the adapters from the environment and exposes the ASGI app."""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from sales.api.app import create_app
from sales.infrastructure.database_probe import SqlAlchemyDatabaseProbe
from sales.infrastructure.repositories import (
    PostgresIdempotencyStore,
    PostgresInventoryRepository,
    PostgresOrderRepository,
)


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable {name}")
    return value


database_url = _required_env("DATABASE_URL")
probe = SqlAlchemyDatabaseProbe(database_url)

# Synchronous engine and sessionmaker for sales domain operations
engine = create_engine(database_url, echo=False)
session_factory = sessionmaker(bind=engine)
session = session_factory()

inventory_repo = PostgresInventoryRepository(session)
order_repo = PostgresOrderRepository(session)
idempotency_store = PostgresIdempotencyStore(session)

app = create_app(
    database_probe=probe,
    inventory_repo=inventory_repo,
    order_repo=order_repo,
    idempotency_store=idempotency_store,
)
