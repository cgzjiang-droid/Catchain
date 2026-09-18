"""Human rubric observations; no implicit quality score or missing-data failure."""

from typing import Literal, Self
from uuid import UUID

from pydantic import Field, StrictStr, model_validator

from catchain.domain.common import ImmutableDomainModel
from catchain.domain.evidence import EvidenceRef


class CriterionJudgment(ImmutableDomainModel):
    criterion_id: StrictStr = Field(pattern=r"^D(0[1-9]|1[0-2])\.C[1-3]$")
    outcome: Literal["supported", "not_supported", "insufficient", "conflicting", "not_applicable"]
    reason: StrictStr = Field(min_length=1)
    fact_ids: tuple[UUID, ...] = ()
    evidence: tuple[EvidenceRef, ...] = ()

    @model_validator(mode="after")
    def validate_basis(self) -> Self:
        if not self.reason.strip():
            raise ValueError("reason cannot be blank")
        if len(set(self.fact_ids)) != len(self.fact_ids):
            raise ValueError("duplicate facts")
        if self.outcome in {"supported", "not_supported", "not_applicable"} and (
            not self.fact_ids or not self.evidence
        ):
            raise ValueError("this judgment needs explicit facts and evidence")
        return self


class JudgmentRequest(ImmutableDomainModel):
    rubric_version: Literal["acm0002-quality-rubric-draft-v2"] = "acm0002-quality-rubric-draft-v2"
    reviewer: StrictStr = Field(min_length=1)
    judgments: tuple[CriterionJudgment, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique(self) -> Self:
        if not self.reviewer.strip():
            raise ValueError("reviewer cannot be blank")
        ids = [j.criterion_id for j in self.judgments]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate criterion judgments")
        return self
