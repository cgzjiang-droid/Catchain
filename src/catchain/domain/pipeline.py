"""Pipeline stage and execution-state models."""

from enum import StrEnum
from typing import Self
from uuid import UUID, uuid4

from pydantic import AwareDatetime, Field, model_validator

from catchain.domain.common import ImmutableDomainModel, Sha256


class PipelineStage(StrEnum):
    DISCOVERED = "discovered"
    DOWNLOADED = "downloaded"
    HASHED = "hashed"
    PARSED = "parsed"
    OCR_REQUIRED = "ocr_required"
    OCR_PARSED = "ocr_parsed"
    BASELINE_EXTRACTED = "baseline_extracted"
    LLM_EXTRACTED = "llm_extracted"
    SCHEMA_VALIDATED = "schema_validated"
    QUALITY_VALIDATED = "quality_validated"
    CANONICALIZED = "canonicalized"
    SCORED = "scored"
    EVALUATED = "evaluated"


class RunStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class PipelineRun(ImmutableDomainModel):
    pipeline_run_id: UUID = Field(default_factory=uuid4)
    stage: PipelineStage
    status: RunStatus
    input_hash: Sha256
    config_hash: Sha256
    started_at: AwareDatetime
    finished_at: AwareDatetime | None = None
    error_code: str | None = None
    error_message: str | None = None

    @model_validator(mode="after")
    def validate_lifecycle(self) -> Self:
        if self.finished_at is not None and self.finished_at < self.started_at:
            raise ValueError("finished_at cannot be before started_at")
        if self.status is RunStatus.RUNNING and self.finished_at is not None:
            raise ValueError("running run cannot have finished_at")
        if self.status is not RunStatus.RUNNING and self.finished_at is None:
            raise ValueError("completed run requires finished_at")
        if self.status is RunStatus.FAILED:
            if not self.error_code or not self.error_message:
                raise ValueError("failed run requires error_code and error_message")
        elif self.error_code is not None or self.error_message is not None:
            raise ValueError("only failed run may contain error details")
        return self
