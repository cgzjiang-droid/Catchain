"""Project-scoped consistency diagnostics with unresolved source authority."""

from typing import Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from catchain.domain.common import ImmutableDomainModel, Sha256
from catchain.domain.documents import DocumentType, Registry
from catchain.domain.extraction import FieldName
from catchain.domain.validation import ExtractionValidationReport


class ValidationInput(ImmutableDomainModel):
    report: ExtractionValidationReport
    source_document_id: UUID
    document_type: DocumentType
    sha256: Sha256
    declared_version: str | None
    retrieved_at: AwareDatetime


class CandidateLink(ImmutableDomainModel):
    validation_run_id: UUID
    observation_index: int = Field(ge=0)


class ConsistencyIssue(ImmutableDomainModel):
    code: str = Field(min_length=1)
    fields: tuple[FieldName, ...] = Field(min_length=1)
    candidates: tuple[CandidateLink, ...]
    message: str = Field(min_length=1)
    status: Literal["unresolved"] = "unresolved"


class ProjectConsistencyReport(ImmutableDomainModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    rule_version: Literal["project-consistency-v1"] = "project-consistency-v1"
    authority_policy: Literal["manual-unresolved-v1"] = "manual-unresolved-v1"
    pipeline_run_id: UUID
    project_id: str = Field(min_length=1)
    registry: Registry
    inputs: tuple[ValidationInput, ...] = Field(min_length=1)
    issues: tuple[ConsistencyIssue, ...]
    cross_document_comparison: Literal["performed", "not_possible"]
    canonical_writes: Literal[0] = 0

    @model_validator(mode="after")
    def check_input_scope_and_links(self) -> Self:
        reports = {item.report.pipeline_run_id: item.report for item in self.inputs}
        if len(reports) != len(self.inputs):
            raise ValueError("duplicate validation inputs")
        for report in reports.values():
            if (report.project_id, report.registry) != (self.project_id, self.registry):
                raise ValueError("cannot mix projects or registries")
        for issue in self.issues:
            for link in issue.candidates:
                report = reports.get(link.validation_run_id)
                if report is None or link.observation_index >= len(report.checks):
                    raise ValueError("candidate link has no matching validation input")
                if report.checks[link.observation_index].observation.field_name not in issue.fields:
                    raise ValueError("candidate link field differs from issue")
        return self
