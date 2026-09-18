"""Runtime configuration and production storage guardrails."""

from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel, ConfigDict

Environment = Literal["development", "test", "production"]


class ConfigurationError(ValueError):
    """Raised when runtime settings cannot satisfy a deployment boundary."""


class RuntimeConfig(BaseModel):
    """Explicit settings shared by database, object storage and workers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    environment: Environment = "development"
    database_url: str
    object_store_uri: str

    @classmethod
    def from_env(cls) -> RuntimeConfig:
        """Load settings without reading secrets from source files."""

        return cls(
            environment=os.getenv("CATCHAIN_ENVIRONMENT", "development"),
            database_url=os.environ.get(
                "CATCHAIN_DATABASE_URL", "sqlite+pysqlite:///data/catchain.sqlite"
            ),
            object_store_uri=os.environ.get("CATCHAIN_OBJECT_STORE_URI", "file:///data/raw"),
        )

    def production_violations(self) -> tuple[str, ...]:
        """Return deployment violations without attempting a network connection."""

        if self.environment != "production":
            return ()
        violations: list[str] = []
        if not self.database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            violations.append("database_url must use PostgreSQL in production")
        if not self.object_store_uri.startswith(("s3://", "gs://", "https://")):
            violations.append("object_store_uri must use remote object storage in production")
        return tuple(violations)

    def require_production_safe(self) -> None:
        """Fail fast when production would otherwise write to local development storage."""

        violations = self.production_violations()
        if violations:
            raise ConfigurationError("; ".join(violations))

