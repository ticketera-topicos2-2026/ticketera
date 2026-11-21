"""Fixtures of the catalog integration tests, which run against the real `catalog` database (D-06).

They run inside the container with `docker compose run --rm catalog pytest`, which starts the database and
sets DATABASE_URL; without it they are skipped. The schema is brought to the latest migration before
each test, and the catalog tables are emptied before and after it.
"""

import os
from collections.abc import Generator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

CATALOG_TABLES = ("idempotency_keys", "event_participants", "event_zones", "events")


def alembic_config() -> Config:
    return Config("alembic.ini")


@pytest.fixture
def engine() -> Generator[Engine]:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL not set; the integration tests need the catalog database")
    engine = create_engine(database_url)
    yield engine
    engine.dispose()


@pytest.fixture
def session_factory(engine: Engine) -> Generator[sessionmaker[Session]]:
    command.upgrade(alembic_config(), "head")
    _empty_tables(engine)
    yield sessionmaker(bind=engine)
    _empty_tables(engine)


def _empty_tables(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {', '.join(CATALOG_TABLES)} CASCADE"))
