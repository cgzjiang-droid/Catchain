"""Validated records for large source datasets."""

from typing import Literal

from pydantic import AwareDatetime, Field, HttpUrl, StrictStr

from catchain.domain.common import ImmutableDomainModel, Sha256
from catchain.domain.documents import DocumentType, Registry


class ManifestRow(ImmutableDomainModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    relative_path: StrictStr = Field(min_length=1)
    size_bytes: int = Field(gt=0)
    sha256: Sha256
    content_type: StrictStr = Field(min_length=1)
    registry: Registry | None = None
    project_id: StrictStr | None = None
    document_type: DocumentType | None = None
    source_url: HttpUrl | None = None
    declared_version: StrictStr | None = None
    sample_split: Literal["development", "validation", "test"] | None = None


class DatasetManifestHeader(ImmutableDomainModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    root_label: StrictStr = Field(min_length=1)
    generated_at: AwareDatetime
    row_count: int = Field(ge=0)
    total_bytes: int = Field(ge=0)


class SampledManifestRow(ManifestRow):
    sample_split: Literal["development", "validation", "test"]
