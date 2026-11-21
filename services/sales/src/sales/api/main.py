"""Composition root: wires the adapters from the environment and exposes the ASGI app."""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from sales.api.app import create_app
from sales.infrastructure.database_probe import SqlAlchemyDatabaseProbe


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable {name}")
    return value


database_url = _required_env("DATABASE_URL")
probe = SqlAlchemyDatabaseProbe(database_url)

# Synchronous engine and sessionmaker: each request creates its own Session via UnitOfWork
engine = create_engine(database_url, echo=False, pool_pre_ping=True)
session_factory = sessionmaker(bind=engine)

app = create_app(
    database_probe=probe,
    session_factory=session_factory,
)
