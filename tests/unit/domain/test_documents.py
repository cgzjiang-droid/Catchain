from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

import catchain.domain as domain


def test_source_document_accepts_traceable_identity() -> None:
    document = domain.SourceDocument(
        registry=domain.Registry.VERRA,
        registry_project_id="VCS-1234",
        source_url="https://registry.example/projects/1234/pdd.pdf",
        document_type=domain.DocumentType.PROJECT_DESCRIPTION,
        title="Project design document",
        discovered_at=datetime(2026, 9, 9, 8, 0, tzinfo=UTC),
    )

    assert document.registry is domain.Registry.VERRA
    assert document.registry_project_id == "VCS-1234"
    assert str(document.source_url).startswith("https://")


def test_source_document_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        domain.SourceDocument(
            registry=domain.Registry.ACR,
            registry_project_id="ACR-1",
            source_url="https://registry.example/acr-1.pdf",
            document_type=domain.DocumentType.OTHER,
            discovered_at=datetime(2026, 9, 9, tzinfo=UTC),
            invented_field="not allowed",
        )


def test_document_version_rejects_uppercase_sha256() -> None:
    with pytest.raises(ValidationError):
        domain.DocumentVersion(
            source_document_id=uuid4(),
            sha256="A" * 64,
            retrieved_at=datetime(2026, 9, 9, tzinfo=UTC),
            content_type="application/pdf",
            file_name="pdd.pdf",
            byte_size=42,
        )


def test_document_version_rejects_non_positive_size() -> None:
    with pytest.raises(ValidationError):
        domain.DocumentVersion(
            source_document_id=uuid4(),
            sha256="a" * 64,
            retrieved_at=datetime(2026, 9, 9, tzinfo=UTC),
            content_type="application/pdf",
            file_name="pdd.pdf",
            byte_size=0,
        )


def test_document_version_is_immutable() -> None:
    version = domain.DocumentVersion(
        source_document_id=uuid4(),
        sha256="a" * 64,
        retrieved_at=datetime(2026, 9, 9, tzinfo=UTC),
        content_type="application/pdf",
        file_name="pdd.pdf",
        byte_size=42,
    )

    with pytest.raises(ValidationError, match="frozen_instance"):
        version.byte_size = 84
