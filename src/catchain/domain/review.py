"""Explicit human decisions; corrected observations retain grounded evidence."""

from typing import Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from catchain.domain.common import ImmutableDomainModel
from catchain.domain.extraction import FieldObservation


class ReviewRequest(ImmutableDomainModel):
    policy_version: Literal["manual-reviewed-v1"] = "manual-reviewed-v1"
    decision_id: UUID
    candidate_id: UUID
    reviewer: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    status: Literal["approved", "rejected", "unresolved"]
    expected_current_fact_id: UUID | None = None
    after: FieldObservation | None = None
    authority_confirmed: bool = False

    @model_validator(mode="after")
    def require_explicit_review(self) -> Self:
        if not self.reviewer.strip() or not self.reason.strip():
            raise ValueError("reviewer and reason cannot be blank")
        if self.status == "approved":
            if not self.authority_confirmed or self.after is None or self.after.missing_reason:
                raise ValueError("approval requires authority confirmation and an evidenced value")
        elif self.after is not None or self.authority_confirmed:
            raise ValueError("non-approval cannot supply a replacement value")
        return self
