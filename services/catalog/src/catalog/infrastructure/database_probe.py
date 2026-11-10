"""SQLAlchemy adapter of the database probe port (DS-11)."""

import logging

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

# Connect plus query stay under the 3-second limit of the spec.
CONNECT_TIMEOUT_SECONDS = 2
QUERY_TIMEOUT_MILLISECONDS = 500


class SqlAlchemyDatabaseProbe:
    """Runs `SELECT 1` with connect and query timeouts."""

    def __init__(self, database_url: str) -> None:
        self._engine = create_engine(
            database_url,
            # Discards pooled connections that died while the database was down, so the
            # service recovers without a restart.
            pool_pre_ping=True,
            connect_args={
                "connect_timeout": CONNECT_TIMEOUT_SECONDS,
                "options": f"-c statement_timeout={QUERY_TIMEOUT_MILLISECONDS}",
            },
        )

    def is_reachable(self) -> bool:
        try:
            with self._engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError as error:
            logger.warning("Database unreachable: %s", type(error).__name__)
            return False
        return True
