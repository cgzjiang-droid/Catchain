"""Verra/VCS JSON response parsing from the audited legacy collector."""

from __future__ import annotations

from urllib.parse import urljoin

from catchain.domain import DocumentType, Registry
from catchain.registries.base import RemoteDocument


def parse_verra_documents(
    *, project_id: str, payload: dict, discovered_at
) -> tuple[RemoteDocument, ...]:
    documents: list[RemoteDocument] = []
    for group in payload.get("documentGroups", []):
        for item in group.get("documents", []):
            uri = item.get("uri")
            if not uri:
                continue
            document_id = str(item.get("id") or uri)
            documents.append(
                RemoteDocument(
                    registry=Registry.VERRA,
                    project_id=project_id,
                    document_id=document_id,
                    document_type=DocumentType.OTHER,
                    title=str(item.get("documentName") or document_id),
                    url=urljoin("https://registry.verra.org/", str(uri)),
                    discovered_at=discovered_at,
                    declared_version=item.get("version"),
                )
            )
    return tuple(documents)

