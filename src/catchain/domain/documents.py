"""Document discovery and content-version models."""

from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import AwareDatetime, Field, HttpUrl

from catchain.domain.common import ImmutableDomainModel, Sha256


class Registry(StrEnum):
    ACR = "acr"
    GOLD_STANDARD = "gold_standard"
    VERRA = "verra"


class DocumentType(StrEnum):
    PROJECT_DESCRIPTION = "project_description"
    MONITORING_REPORT = "monitoring_report"
    VALIDATION_REPORT = "validation_report"
    VERIFICATION_REPORT = "verification_report"
    REGISTRY_EXPORT = "registry_export"
    OTHER = "other"


class SourceDocument(ImmutableDomainModel):
    source_document_id: UUID = Field(default_factory=uuid4)
    registry: Registry
    registry_project_id: str = Field(min_length=1)
    source_url: HttpUrl
    document_type: DocumentType
    title: str | None = None
    discovered_at: AwareDatetime


class DocumentVersion(ImmutableDomainModel):
    document_version_id: UUID = Field(default_factory=uuid4)
    source_document_id: UUID
    sha256: Sha256
    retrieved_at: AwareDatetime
    content_type: str = Field(min_length=1)
    file_name: str = Field(min_length=1)
    byte_size: int = Field(gt=0)
    declared_version: str | None = None
