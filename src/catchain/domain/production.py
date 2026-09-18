"""Explicit production readiness contracts; local MVP state is never inferred as ready."""

from typing import Literal

from pydantic import Field, StrictStr

from catchain.domain.common import ImmutableDomainModel


class ProductionCheck(ImmutableDomainModel):
    code: StrictStr = Field(min_length=1)
    status: Literal["pass", "blocked"]
    evidence: StrictStr = Field(min_length=1)


class ProductionChecklist(ImmutableDomainModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    status: Literal["ready", "blocked"]
    checks: tuple[ProductionCheck, ...] = Field(min_length=1)
    blockers: tuple[StrictStr, ...] = ()

