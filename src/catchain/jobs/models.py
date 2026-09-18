"""Typed state for processing jobs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class JobKind(StrEnum):
    INGEST = "ingest"
    PARSE = "parse"
    EXTRACT = "extract"
    VALIDATE = "validate"


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    RETRY = "retry"
    DEAD_LETTER = "dead_letter"


@dataclass(frozen=True, slots=True)
class Job:
    job_id: str
    kind: JobKind
    input_identity: str
    payload: dict[str, Any]
    status: JobStatus
    attempts: int
    max_attempts: int
    next_retry_at: datetime | None
    last_error: str | None

