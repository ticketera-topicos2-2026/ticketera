"""Composition root: wires the adapters from the environment and exposes the ASGI app."""

import os

from catalog.api.app import create_app
from catalog.infrastructure.database_probe import SqlAlchemyDatabaseProbe


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable {name}")
    return value


app = create_app(SqlAlchemyDatabaseProbe(_required_env("DATABASE_URL")))
