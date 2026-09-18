"""Versioned, score-free evaluation result contracts for the draft rubric."""

from typing import Literal, Self

from pydantic import Field, StrictStr, model_validator

from catchain.domain.common import ImmutableDomainModel, Sha256
from catchain.domain.judgment import CriterionJudgment, JudgmentRequest


class DimensionEvaluation(ImmutableDomainModel):
    dimension_id: StrictStr = Field(pattern=r"^D(0[1-9]|1[0-2])$")
    name: StrictStr = Field(min_length=1)
    criterion_ids: tuple[StrictStr, ...] = Field(min_length=1)
    reviewed_criterion_ids: tuple[StrictStr, ...] = ()
    unreviewed_criterion_ids: tuple[StrictStr, ...] = ()
    judgments: tuple[CriterionJudgment, ...] = ()
    status: Literal[
        "unreviewed", "partially_reviewed", "unresolved", "reviewed_pending_policy"
    ]
    score: None = None
    weight: float | None = None

    @model_validator(mode="after")
    def validate_coverage(self) -> Self:
        criterion_ids = set(self.criterion_ids)
        reviewed = set(self.reviewed_criterion_ids)
        unreviewed = set(self.unreviewed_criterion_ids)
        judged = {judgment.criterion_id for judgment in self.judgments}
        if len(self.criterion_ids) != len(criterion_ids):
            raise ValueError("duplicate criterion ids")
        if reviewed & unreviewed or reviewed | unreviewed != criterion_ids:
            raise ValueError("dimension coverage is not a partition")
        if judged != reviewed:
            raise ValueError("judgments do not match reviewed criteria")
        unresolved = {j.outcome for j in self.judgments} & {"insufficient", "conflicting"}
        expected = (
            "unreviewed"
            if not reviewed
            else "partially_reviewed"
            if unreviewed
            else "unresolved"
            if unresolved
            else "reviewed_pending_policy"
        )
        if self.status != expected:
            raise ValueError("dimension status does not match coverage")
        return self


class EvaluationResult(ImmutableDomainModel):
    schema_version: Literal["1.1.0"] = "1.1.0"
    rubric_version: Literal["acm0002-quality-rubric-draft-v2"]
    rubric_sha256: Sha256
    rubric_status: StrictStr = Field(min_length=1)
    request: JudgmentRequest
    input_readiness: dict[str, object]
    unreviewed_criteria: tuple[StrictStr, ...]
    dimensions: tuple[DimensionEvaluation, ...] = Field(min_length=12, max_length=12)
    score_status: Literal["pending_policy"]
    total_score: None = None
    model_calls: int = Field(default=0, ge=0)
    limitations: tuple[StrictStr, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_dimensions(self) -> Self:
        expected = {f"D{i:02d}" for i in range(1, 13)}
        actual = {dimension.dimension_id for dimension in self.dimensions}
        if actual != expected:
            raise ValueError("evaluation must contain exactly D01-D12")
        all_criteria = {
            criterion_id
            for dimension in self.dimensions
            for criterion_id in dimension.criterion_ids
        }
        reviewed = {
            criterion_id
            for dimension in self.dimensions
            for criterion_id in dimension.reviewed_criterion_ids
        }
        if set(self.unreviewed_criteria) != all_criteria - reviewed:
            raise ValueError("unreviewed criteria do not match dimension coverage")
        return self
