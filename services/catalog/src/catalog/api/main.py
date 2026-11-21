"""Composition root: wires the adapters from the environment and exposes the ASGI app."""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from catalog.api.app import create_app
from catalog.infrastructure.database_probe import SqlAlchemyDatabaseProbe
from catalog.infrastructure.uow import SqlAlchemyUnitOfWork


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable {name}")
    return value


database_url = _required_env("DATABASE_URL")
# One engine for the process; each use case opens its own session and transaction (unit of work).
session_factory = sessionmaker(bind=create_engine(database_url, pool_pre_ping=True))

app = create_app(
    SqlAlchemyDatabaseProbe(database_url),
    uow_factory=lambda: SqlAlchemyUnitOfWork(session_factory),
)
