"""Activation gate for scoring policies; draft policies cannot produce totals."""

from datetime import date
from typing import Literal, Self

from pydantic import Field, HttpUrl, StrictStr, model_validator

from catchain.domain.common import ImmutableDomainModel


class DimensionWeight(ImmutableDomainModel):
    dimension_id: StrictStr = Field(pattern=r"^D(0[1-9]|1[0-2])$")
    weight: float | None = Field(default=None, ge=0, le=1)


class ScoringPolicy(ImmutableDomainModel):
    """A versioned 12-dimension policy with an explicit approval boundary."""

    schema_version: Literal["1.0.0"] = "1.0.0"
    policy_version: StrictStr = Field(min_length=1)
    rubric_version: StrictStr = Field(min_length=1)
    status: Literal["draft", "approved", "retired"] = "draft"
    dimensions: tuple[DimensionWeight, ...] = Field(min_length=12, max_length=12)
    authority_sources: tuple[HttpUrl, ...] = ()
    approved_by: StrictStr | None = None
    approved_on: date | None = None

    @model_validator(mode="after")
    def validate_activation(self) -> Self:
        expected = {f"D{i:02d}" for i in range(1, 13)}
        actual = {dimension.dimension_id for dimension in self.dimensions}
        if actual != expected:
            raise ValueError("scoring policy must contain exactly D01-D12")
        if len(actual) != len(self.dimensions):
            raise ValueError("duplicate scoring policy dimensions")
        weights = [dimension.weight for dimension in self.dimensions]
        if self.status == "approved":
            if any(weight is None for weight in weights):
                raise ValueError("approved policy requires every dimension weight")
            if abs(sum(weight for weight in weights if weight is not None) - 1) > 1e-9:
                raise ValueError("approved policy weights must sum to 1")
            if not self.authority_sources or not self.approved_by or not self.approved_on:
                raise ValueError("approved policy requires sources, reviewer and date")
        return self
