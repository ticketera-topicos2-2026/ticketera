"""SQLAlchemy implementation of UnitOfWork."""

from sqlalchemy.orm import Session, sessionmaker

from sales.application.uow import UnitOfWork
from sales.infrastructure.repositories import (
    PostgresIdempotencyStore,
    PostgresInventoryRepository,
    PostgresOrderRepository,
)


class SqlAlchemyUnitOfWork(UnitOfWork):
    """SQLAlchemy unit of work managing a transaction per request."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory
        self.session: Session | None = None

    def __enter__(self) -> "SqlAlchemyUnitOfWork":
        self.session = self.session_factory()
        self.inventory_repo = PostgresInventoryRepository(self.session)
        self.order_repo = PostgresOrderRepository(self.session)
        self.idempotency_store = PostgresIdempotencyStore(self.session)
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        if self.session is not None:
            if exc_type is not None:
                self.rollback()
            self.session.close()

    def commit(self) -> None:
        if self.session is not None:
            self.session.commit()

    def rollback(self) -> None:
        if self.session is not None:
            self.session.rollback()
