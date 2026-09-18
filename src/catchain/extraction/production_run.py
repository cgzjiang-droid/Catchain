"""Production-facing structured extraction boundary with evidence revalidation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from catchain.domain import ParsedDocument, ProjectExtraction, Registry
from catchain.extraction.llm.contract import FieldName, StructuredProvider
from catchain.extraction.llm.workflow import ExtractionArtifact, extract_one_call


@dataclass(frozen=True, slots=True)
class GroundingReport:
    valid: bool
    checked_evidence: int
    issues: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProductionExtraction:
    extraction: ProjectExtraction
    artifact: ExtractionArtifact
    grounding: GroundingReport


def validate_grounding(extraction: ProjectExtraction, parsed: ParsedDocument) -> GroundingReport:
    """Verify every stored evidence offset against the immutable parsed page text."""

    issues: list[str] = []
    checked = 0
    if extraction.document_version_id != parsed.document_version_id:
        issues.append("document_version_mismatch")
    pages = {page.page_number: page.text for page in parsed.pages}
    for observation in extraction.observations:
        for evidence in observation.evidence:
            checked += 1
            text = pages.get(evidence.page_number)
            if text is None:
                issues.append(f"missing_page:{evidence.page_number}")
                continue
            if evidence.char_start is None or evidence.char_end is None:
                issues.append(f"missing_offsets:{evidence.page_number}")
                continue
            if text[evidence.char_start : evidence.char_end] != evidence.quote:
                issues.append(f"quote_mismatch:{evidence.page_number}")
    return GroundingReport(valid=not issues, checked_evidence=checked, issues=tuple(issues))


def run_structured_extraction(
    document: ParsedDocument,
    *,
    fields: tuple[FieldName, ...],
    provider: StructuredProvider,
    page_numbers: tuple[int, ...],
    project_id: str,
    registry: Registry,
    output_dir: Path,
) -> ProductionExtraction:
    """Run the existing bounded call, then revalidate its persisted result."""

    artifact = extract_one_call(
        document,
        provider=provider,
        page_numbers=page_numbers,
        requested_fields=fields,
        project_id=project_id,
        registry=registry,
        output_dir=output_dir,
    )
    payload = json.loads(artifact.path.read_text(encoding="utf-8"))
    extraction = ProjectExtraction.model_validate(payload["result"])
    grounding = validate_grounding(extraction, document)
    if not grounding.valid:
        raise ValueError("persisted extraction failed evidence grounding")
    return ProductionExtraction(extraction=extraction, artifact=artifact, grounding=grounding)

