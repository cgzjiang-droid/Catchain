"""Shared candidate contract for regex and future LLM extraction."""

from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, Field, StrictBool, StrictInt, StrictStr, model_validator

from catchain.domain.common import ImmutableDomainModel
from catchain.domain.documents import Registry
from catchain.domain.evidence import EvidenceRef

FieldName = Literal[
    "project_id",
    "project_name",
    "country",
    "grid_connection_status",
    "project_boundary_text",
    "technology_type",
    "installed_capacity_mw",
    "renewable_resource_type",
    "baseline_scenario_text",
    "baseline_formula_present",
    "baseline_assumptions_table",
    "ef_value",
    "ef_unit",
    "ef_source_reference",
    "ef_vintage_year",
    "electricity_generated_mwh",
    "electricity_exported_mwh",
    "meter_calibration_status",
    "data_frequency",
    "pe_applicable_flag",
    "pe_value_tco2e",
    "pe_method_text",
    "le_applicable_flag",
    "le_value_tco2e",
    "le_justification_text",
    "be_value_tco2e",
    "er_reported_tco2e",
    "er_recalculated_tco2e",
    "er_recalc_error_pct",
    "additionality_tool_used",
    "investment_analysis_result",
    "barrier_analysis_result",
    "common_practice_result",
    "monitoring_parameters_listed",
    "qa_qc_procedure_text",
    "data_gap_procedure_text",
    "archiving_period_years",
    "validator_name",
    "verifier_name",
    "verification_period_start",
    "verification_period_end",
    "verification_cycle_count",
    "methodology_name",
    "methodology_version",
    "registered_date",
    "listed_date",
    "issuance_cycle_count",
    "version_change_note",
    "project_participant",
    "project_owner",
    "project_developer",
    "project_operator",
    "crediting_period_years",
    "crediting_period_start",
    "crediting_period_end",
]
CandidateValue = (
    StrictStr | StrictInt | StrictBool | Annotated[float, Field(strict=True, allow_inf_nan=False)]
)


class FieldObservation(ImmutableDomainModel):
    """An unvalidated candidate or explicit abstention; never a canonical fact."""

    field_name: FieldName
    raw_value: StrictStr | None = Field(default=None, min_length=1)
    normalized_value: CandidateValue | None = None
    unit: str | None = Field(default=None, min_length=1)
    confidence: float | None = Field(default=None, ge=0, le=1)
    evidence: tuple[EvidenceRef, ...] = ()
    missing_reason: Literal["not_found", "unsupported_by_baseline", "ambiguous"] | None = None
    issues: tuple[str, ...] = ()
    validation_status: Literal["unvalidated"] = "unvalidated"

    @model_validator(mode="after")
    def validate_candidate_or_abstention(self) -> Self:
        if self.missing_reason is None:
            if self.raw_value is None or self.normalized_value is None or not self.evidence:
                raise ValueError("candidates require raw/normalized values and evidence")
        elif self.raw_value is not None or self.normalized_value is not None:
            raise ValueError("missing observations cannot carry a value")
        return self


class ProjectExtraction(ImmutableDomainModel):
    """Versioned extraction from one Parsed artifact; conflicting candidates survive."""

    project_id: str = Field(min_length=1)
    registry: Registry
    document_version_id: UUID
    parsed_document_id: UUID
    extractor_name: str = Field(min_length=1)
    extractor_version: str = Field(min_length=1)
    schema_version: Literal["1.0.0", "1.1.0"] = "1.1.0"
    pipeline_run_id: UUID | None = None
    created_at: AwareDatetime
    observations: tuple[FieldObservation, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_evidence_version(self) -> Self:
        if self.schema_version == "1.1.0" and self.pipeline_run_id is None:
            raise ValueError("schema 1.1.0 requires a processing run identity")
        for observation in self.observations:
            if any(
                evidence.document_version_id != self.document_version_id
                for evidence in observation.evidence
            ):
                raise ValueError("evidence must refer to the extracted document version")
        return self
