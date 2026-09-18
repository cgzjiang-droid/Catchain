"""Small SQLAlchemy-backed job store used by workers and resumable batches."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import Engine, insert, select, update

from catchain.jobs.models import Job, JobKind, JobStatus
from catchain.jobs.retry import RetryPolicy
from catchain.storage.database import processing_jobs


class JobStore:
    """Persist job state in the same database as document provenance."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def enqueue(
        self,
        *,
        kind: JobKind,
        input_identity: str,
        payload: dict[str, Any] | None = None,
        max_attempts: int = 3,
    ) -> Job:
        payload = payload or {}
        with self.engine.begin() as connection:
            existing = connection.execute(
                select(processing_jobs).where(
                    processing_jobs.c.kind == kind.value,
                    processing_jobs.c.input_identity == input_identity,
                )
            ).mappings().first()
            if existing is None:
                job_id = str(uuid4())
                connection.execute(
                    insert(processing_jobs).values(
                        job_id=job_id,
                        kind=kind.value,
                        input_identity=input_identity,
                        payload_json=json.dumps(payload, sort_keys=True),
                        status=JobStatus.PENDING.value,
                        attempts=0,
                        max_attempts=max_attempts,
                        next_retry_at=None,
                        last_error=None,
                        created_at=datetime.now(UTC).isoformat(),
                    )
                )
                existing = connection.execute(
                    select(processing_jobs).where(processing_jobs.c.job_id == job_id)
                ).mappings().one()
        return _to_job(existing)

    def claim_next(self, *, now: datetime | None = None) -> Job | None:
        now = now or datetime.now(UTC)
        with self.engine.begin() as connection:
            row = connection.execute(
                select(processing_jobs)
                .where(
                    processing_jobs.c.status.in_((JobStatus.PENDING.value, JobStatus.RETRY.value)),
                    (processing_jobs.c.next_retry_at.is_(None))
                    | (processing_jobs.c.next_retry_at <= now.isoformat()),
                )
                .order_by(processing_jobs.c.created_at)
                .limit(1)
            ).mappings().first()
            if row is None:
                return None
            updated = connection.execute(
                update(processing_jobs)
                .where(
                    processing_jobs.c.job_id == row["job_id"],
                    processing_jobs.c.status.in_((JobStatus.PENDING.value, JobStatus.RETRY.value)),
                )
                .values(status=JobStatus.RUNNING.value)
            )
            if updated.rowcount != 1:
                return None
            row = dict(row)
            row["status"] = JobStatus.RUNNING.value
        return _to_job(row)

    def mark_succeeded(self, job_id: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                update(processing_jobs)
                .where(processing_jobs.c.job_id == job_id)
                .values(status=JobStatus.SUCCEEDED.value, last_error=None)
            )

    def mark_failed(
        self,
        job: Job,
        *,
        error_code: str,
        error_message: str,
        policy: RetryPolicy,
        now: datetime | None = None,
    ) -> Job:
        now = now or datetime.now(UTC)
        attempt = job.attempts + 1
        decision = policy.next_attempt(attempt=attempt, error_code=error_code)
        status = JobStatus.RETRY if decision.retry else JobStatus.DEAD_LETTER
        next_retry = now + timedelta(seconds=decision.delay_seconds) if decision.retry else None
        with self.engine.begin() as connection:
            connection.execute(
                update(processing_jobs)
                .where(processing_jobs.c.job_id == job.job_id)
                .values(
                    status=status.value,
                    attempts=attempt,
                    next_retry_at=next_retry.isoformat() if next_retry else None,
                    last_error=f"{error_code}:{error_message}",
                )
            )
            row = connection.execute(
                select(processing_jobs).where(processing_jobs.c.job_id == job.job_id)
            ).mappings().one()
        return _to_job(row)


def _to_job(row: Any) -> Job:
    next_retry = row["next_retry_at"]
    return Job(
        job_id=row["job_id"],
        kind=JobKind(row["kind"]),
        input_identity=row["input_identity"],
        payload=json.loads(row["payload_json"]),
        status=JobStatus(row["status"]),
        attempts=row["attempts"],
        max_attempts=row["max_attempts"],
        next_retry_at=datetime.fromisoformat(next_retry) if next_retry else None,
        last_error=row["last_error"],
    )

