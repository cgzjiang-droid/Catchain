"""Explicit gates for version reprocessing before canonical promotion."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

REQUIRED_VERSION_STAGES = ("parsed", "extracted", "validated", "reviewed")


@dataclass(frozen=True, slots=True)
class VersionReprocessGate:
    previous_document_version_id: UUID | None
    current_document_version_id: UUID
    completed_stages: tuple[str, ...]
    missing_stages: tuple[str, ...]

    @property
    def eligible_for_canonical_promotion(self) -> bool:
        return not self.missing_stages


def require_version_reprocess(
    *,
    current_document_version_id: UUID,
    previous_document_version_id: UUID | None,
    completed_stages: tuple[str, ...],
) -> VersionReprocessGate:
    """Require the complete workflow whenever the source version changes."""

    unknown = set(completed_stages) - set(REQUIRED_VERSION_STAGES)
    if unknown:
        raise ValueError(f"unknown reprocess stages: {sorted(unknown)}")
    if previous_document_version_id == current_document_version_id:
        raise ValueError("current document version must be newer than previous version")
    completed = tuple(stage for stage in REQUIRED_VERSION_STAGES if stage in completed_stages)
    missing = tuple(stage for stage in REQUIRED_VERSION_STAGES if stage not in completed)
    return VersionReprocessGate(
        previous_document_version_id=previous_document_version_id,
        current_document_version_id=current_document_version_id,
        completed_stages=completed,
        missing_stages=missing,
    )

