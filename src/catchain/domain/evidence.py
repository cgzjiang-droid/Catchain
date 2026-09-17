"""References from extracted facts back to source text."""

from typing import Self
from uuid import UUID

from pydantic import Field, model_validator

from catchain.domain.common import ImmutableDomainModel


class EvidenceRef(ImmutableDomainModel):
    document_version_id: UUID
    page_number: int = Field(ge=1)
    quote: str = Field(min_length=1)
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_offsets(self) -> Self:
        if (self.char_start is None) != (self.char_end is None):
            raise ValueError("char_start and char_end must be provided together")
        if (
            self.char_start is not None
            and self.char_end is not None
            and self.char_end <= self.char_start
        ):
            raise ValueError("char_end must be greater than char_start")
        return self
