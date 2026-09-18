"""Production PostgreSQL engine boundary.

SQLite remains the deliberate development/offline implementation. Production code
must construct this wrapper so a local file database cannot be selected by accident.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from catchain.config import ConfigurationError, RuntimeConfig


@dataclass
class ProductionDatabase:
    """Lazy PostgreSQL database handle with a session factory."""

    database_url: str
    _engine: Engine | None = None

    @classmethod
    def from_config(
        cls, config: RuntimeConfig, *, create_engine: bool = True
    ) -> ProductionDatabase:
        if config.environment != "production":
            raise ConfigurationError("ProductionDatabase requires environment=production")
        config.require_production_safe()
        instance = cls(database_url=config.database_url)
        if create_engine:
            instance._engine = instance._create_engine()
        return instance

    def _create_engine(self) -> Engine:
        return create_engine(
            self.database_url,
            pool_pre_ping=True,
            pool_recycle=1800,
            future=True,
        )

    @property
    def engine(self) -> Engine:
        if self._engine is None:
            self._engine = self._create_engine()
        return self._engine

    def create_session(self) -> Session:
        """Create one unit-of-work session; callers own commit/rollback/close."""

        return sessionmaker(bind=self.engine, expire_on_commit=False)()

