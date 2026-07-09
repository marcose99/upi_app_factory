from __future__ import annotations

from .ports import DisputeRepositoryPort


class LocalSqliteUnitOfWork:
    def __init__(self, repository: DisputeRepositoryPort) -> None:
        self.repository = repository

    def commit(self) -> None:
        connection = getattr(self.repository, "connection", None)
        if connection is not None:
            connection.commit()

    def rollback(self) -> None:
        connection = getattr(self.repository, "connection", None)
        if connection is not None:
            connection.rollback()
