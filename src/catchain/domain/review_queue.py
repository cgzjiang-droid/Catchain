"""Validated projections used by the human review queue and metrics snapshot."""

from typing import Any, Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, StrictStr

from catchain.domain.common import ImmutableDomainModel
from catchain.domain.documents import Registry
from catchain.domain.evidence import EvidenceRef


class ReviewQueueItem(ImmutableDomainModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    candidate_id: UUID
    validation_run_id: UUID
    registry: Registry
    project_id: StrictStr = Field(min_length=1)
    field_name: StrictStr = Field(min_length=1)
    validation_status: Literal["missing", "rejected", "needs_review"]
    review_state: Literal["pending", "approved", "rejected", "unresolved"]
    priority: Literal["critical", "high", "normal", "low"]
    priority_score: int = Field(ge=0)
    priority_reasons: tuple[StrictStr, ...] = ()
    value: Any = None
    unit: StrictStr | None = None
    issue_codes: tuple[StrictStr, ...] = ()
    issues: tuple[dict[str, Any], ...] = ()
    evidence: tuple[EvidenceRef, ...] = ()
    evidence_count: int = Field(ge=0)
    current_fact_id: UUID | None = None
    decision_count: int = Field(ge=0)
    latest_decision_at: AwareDatetime | None = None


class ReviewQueueSnapshot(ImmutableDomainModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    generated_at: AwareDatetime
    project_id: StrictStr | None = None
    field_name: StrictStr | None = None
    include_approved: bool = False
    items: tuple[ReviewQueueItem, ...] = ()
    counts_by_review_state: dict[str, int]
    counts_by_priority: dict[str, int]


class ReviewMetricsSnapshot(ImmutableDomainModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    generated_at: AwareDatetime
    total_candidates: int = Field(ge=0)
    candidates_by_validation_status: dict[str, int]
    reviewed_candidates: int = Field(ge=0)
    pending_candidates: int = Field(ge=0)
    decisions: int = Field(ge=0)
    decisions_by_status: dict[str, int]
    approval_rate: float | None = Field(default=None, ge=0, le=1)
    unresolved_rate: float | None = Field(default=None, ge=0, le=1)
    evidence_coverage: float | None = Field(default=None, ge=0, le=1)
    field_coverage: float | None = Field(default=None, ge=0, le=1)
    rework_candidate_count: int = Field(ge=0)
    average_review_latency_seconds: float | None = Field(default=None, ge=0)
    accuracy_eligible: Literal[False] = False
    total_score_eligible: Literal[False] = False
