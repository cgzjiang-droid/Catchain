"""Validation outcomes retain candidates; none automatically becomes a canonical fact."""

from typing import Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from catchain.domain.common import ImmutableDomainModel
from catchain.domain.documents import Registry
from catchain.domain.extraction import FieldObservation


class ValidationIssue(ImmutableDomainModel):
    code: str = Field(min_length=1)
    severity: Literal["error", "review"]
    message: str = Field(min_length=1)


class CandidateValidation(ImmutableDomainModel):
    observation_index: int = Field(ge=0)
    observation: FieldObservation
    status: Literal["missing", "rejected", "needs_review"]
    issues: tuple[ValidationIssue, ...]

    @model_validator(mode="after")
    def check_status(self) -> Self:
        has_error = any(issue.severity == "error" for issue in self.issues)
        if (self.status == "rejected") != has_error:
            raise ValueError("rejected status requires an error and errors require rejection")
        if self.status == "missing" and self.observation.missing_reason is None:
            raise ValueError("missing status requires an abstention")
        return self


class ExtractionValidationReport(ImmutableDomainModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    validator_version: Literal["candidate-mechanical-v1"] = "candidate-mechanical-v1"
    pipeline_run_id: UUID
    extraction_run_id: UUID
    parsed_document_id: UUID
    document_version_id: UUID
    project_id: str = Field(min_length=1)
    registry: Registry
    checks: tuple[CandidateValidation, ...] = Field(min_length=1)
    canonical_writes: Literal[0] = 0

    @model_validator(mode="after")
    def check_indices(self) -> Self:
        if [check.observation_index for check in self.checks] != list(range(len(self.checks))):
            raise ValueError("candidate indices must preserve original observation order")
        return self
