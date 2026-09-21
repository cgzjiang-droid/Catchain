"""Durable registry sync runs and replay-safe checkpoints."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from uuid import uuid4

from sqlalchemy import Engine, insert, select

from catchain.domain import Registry
from catchain.storage.database import registry_sync_checkpoints, registry_sync_runs
from catchain.sync.service import SyncCheckpoint, SyncFailure, SyncReport


@dataclass(frozen=True, slots=True)
class SyncRunRecord:
    sync_run_id: str
    registry: Registry
    cursor_before: str | None
    cursor_after: str | None
    status: str
    discovered_projects: int
    discovered_documents: int
    failures: tuple[SyncFailure, ...]
    started_at: datetime
    finished_at: datetime


class SyncRepository:
    """Persist a run before advancing its cursor."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def load_checkpoint(self, registry: Registry) -> SyncCheckpoint:
        with self.engine.begin() as connection:
            row = connection.execute(
                select(registry_sync_checkpoints).where(
                    registry_sync_checkpoints.c.registry == registry.value
                )
            ).mappings().first()
        return SyncCheckpoint(row["cursor"] if row else None)

    def record_run(
        self,
        *,
        registry: Registry,
        checkpoint_before: SyncCheckpoint,
        report: SyncReport,
        started_at: datetime,
        finished_at: datetime | None = None,
    ) -> SyncRunRecord:
        finished_at = finished_at or started_at
        sync_run_id = str(uuid4())
        # A page with failures must be replayed from its previous cursor.
        cursor_after = (
            report.next_checkpoint.cursor
            if not report.failures
            else checkpoint_before.cursor
        )
        record = SyncRunRecord(
            sync_run_id=sync_run_id,
            registry=registry,
            cursor_before=checkpoint_before.cursor,
            cursor_after=cursor_after,
            status=report.status,
            discovered_projects=report.discovered_projects,
            discovered_documents=len(report.discovered_documents),
            failures=report.failures,
            started_at=started_at,
            finished_at=finished_at,
        )
        payload = [asdict(failure) for failure in record.failures]
        with self.engine.begin() as connection:
            connection.execute(
                insert(registry_sync_runs).values(
                    sync_run_id=record.sync_run_id,
                    registry=record.registry.value,
                    cursor_before=record.cursor_before,
                    cursor_after=record.cursor_after,
                    status=record.status,
                    discovered_projects=record.discovered_projects,
                    discovered_documents=record.discovered_documents,
                    failures_json=json.dumps(payload, sort_keys=True),
                    started_at=record.started_at.isoformat(),
                    finished_at=record.finished_at.isoformat(),
                )
            )
            connection.execute(
                registry_sync_checkpoints.delete().where(
                    registry_sync_checkpoints.c.registry == record.registry.value
                )
            )
            connection.execute(
                insert(registry_sync_checkpoints).values(
                    registry=record.registry.value,
                    cursor=record.cursor_after,
                    last_run_id=record.sync_run_id,
                    status=record.status,
                    updated_at=record.finished_at.isoformat(),
                )
            )
        return record

    def latest_run(self, registry: Registry) -> SyncRunRecord:
        with self.engine.begin() as connection:
            row = connection.execute(
                select(registry_sync_runs)
                .where(registry_sync_runs.c.registry == registry.value)
                .order_by(registry_sync_runs.c.finished_at.desc())
                .limit(1)
            ).mappings().one()
        failures = tuple(SyncFailure(**item) for item in json.loads(row["failures_json"]))
        return SyncRunRecord(
            sync_run_id=row["sync_run_id"],
            registry=Registry(row["registry"]),
            cursor_before=row["cursor_before"],
            cursor_after=row["cursor_after"],
            status=row["status"],
            discovered_projects=row["discovered_projects"],
            discovered_documents=row["discovered_documents"],
            failures=failures,
            started_at=datetime.fromisoformat(row["started_at"]),
            finished_at=datetime.fromisoformat(row["finished_at"]),
        )
