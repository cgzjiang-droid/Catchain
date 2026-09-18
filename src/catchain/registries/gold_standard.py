"""Gold Standard project-document response parsing."""

from __future__ import annotations

from catchain.domain import DocumentType, Registry
from catchain.registries.base import RemoteDocument


def parse_gold_documents(
    *, project_id: str, payload: dict, discovered_at
) -> tuple[RemoteDocument, ...]:
    documents: list[RemoteDocument] = []
    for request in payload.get("requests", []):
        for item in request.get("documents", []):
            identifier = item.get("id")
            if identifier is None:
                continue
            document_id = str(identifier)
            documents.append(
                RemoteDocument(
                    registry=Registry.GOLD_STANDARD,
                    project_id=project_id,
                    document_id=document_id,
                    document_type=DocumentType.OTHER,
                    title=str(item.get("name") or document_id),
                    url=(
                        "https://assurance-platform.goldstandard.org/"
                        f"api/public/documents/{document_id}/download"
                    ),
                    discovered_at=discovered_at,
                )
            )
    return tuple(documents)

