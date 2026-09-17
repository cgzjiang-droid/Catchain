"""Constraints shared by CATchain domain models."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class ImmutableDomainModel(BaseModel):
    """Base class for validated immutable domain values."""

    model_config = ConfigDict(extra="forbid", frozen=True)
