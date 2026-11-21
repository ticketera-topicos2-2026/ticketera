"""SQLAlchemy unit of work of the catalog: one session and one transaction per use case (D-33)."""

from typing import Self

from sqlalchemy.orm import Session, sessionmaker

from catalog.infrastructure.repositories import SqlAlchemyEventRepository, SqlAlchemyIdempotencyStore


class SqlAlchemyUnitOfWork:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None

    def __enter__(self) -> Self:
        self._session = self._session_factory()
        self._events = SqlAlchemyEventRepository(self._session)
        self._idempotency = SqlAlchemyIdempotencyStore(self._session)
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        if self._session is None:
            return
        # Anything not committed is discarded, also when the use case ends without an exception.
        self._session.rollback()
        self._session.close()
        self._session = None

    @property
    def events(self) -> SqlAlchemyEventRepository:
        return self._events

    @property
    def idempotency(self) -> SqlAlchemyIdempotencyStore:
        return self._idempotency

    def commit(self) -> None:
        if self._session is not None:
            self._session.commit()

    def rollback(self) -> None:
        if self._session is not None:
            self._session.rollback()
