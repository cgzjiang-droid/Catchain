"""Human-attested context binding an assessment to exact reviewed facts."""

from datetime import date
from typing import Literal, Self
from uuid import UUID

from pydantic import Field, StrictStr, model_validator

from catchain.domain.common import ImmutableDomainModel
from catchain.domain.evidence import EvidenceRef
from catchain.domain.extraction import FieldName


class AssessmentContext(ImmutableDomainModel):
    policy_version: Literal["business-gates-v1"] = "business-gates-v1"
    reviewer: StrictStr = Field(min_length=1)
    reason: StrictStr = Field(min_length=1)
    authority_confirmed: bool
    methodology_fact_id: UUID
    methodology_version_fact_id: UUID
    period_start: StrictStr
    period_end: StrictStr
    period_fact_ids: dict[FieldName, UUID] = Field(min_length=1)
    evidence: tuple[EvidenceRef, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_period(self) -> Self:
        if not self.reviewer.strip() or not self.reason.strip():
            raise ValueError("reviewer and reason cannot be blank")
        dates = []
        for value in (self.period_start, self.period_end):
            parsed = date.fromisoformat(value)
            if parsed.isoformat() != value:
                raise ValueError("require complete YYYY-MM-DD")
            dates.append(parsed)
        if dates[0] > dates[1]:
            raise ValueError("period start is after end")
        allowed = {
            "electricity_generated_mwh",
            "electricity_exported_mwh",
            "be_value_tco2e",
            "pe_value_tco2e",
            "le_value_tco2e",
            "er_reported_tco2e",
        }
        if not set(self.period_fact_ids) <= allowed:
            raise ValueError("period bindings only support source measurements")
        if len(set(self.period_fact_ids.values())) != len(self.period_fact_ids):
            raise ValueError("each field needs its own fact identity")
        return self
