"""Page-based migration of audited legacy scalar rules, not a final fact extractor."""

import re
from datetime import UTC, datetime
from typing import get_args
from uuid import UUID

from catchain.domain import (
    EvidenceRef,
    FieldObservation,
    ParsedDocument,
    ProjectExtraction,
    Registry,
)
from catchain.domain.extraction import FieldName

# Each tuple defines patterns, normalization kind and an observed unit.
RULES = {
    "project_name": (
        (
            r"(?m)^[ \t]*(?:project title|title of project activity|project activity title|"
            r"name of the project activity)[ \t]*[:\-–][ \t]*([^\n\r]+)",
        ),
        "title",
        None,
    ),
    "project_participant": (
        (
            r"(?m)^[ \t]*(?:project participants?|project proponents?|authorized participants?)"
            r"[ \t]*[:\-–][ \t]*([^\n\r]+)",
        ),
        "company",
        None,
    ),
    "project_owner": (
        (r"(?m)^[ \t]*project owners?[ \t]*[:\-–][ \t]*([^\n\r]+)",),
        "company",
        None,
    ),
    "project_developer": (
        (r"(?m)^[ \t]*project developer[ \t]*[:\-–][ \t]*([^\n\r]+)",),
        "company",
        None,
    ),
    "project_operator": (
        (r"(?m)^[ \t]*project operator[ \t]*[:\-–][ \t]*([^\n\r]+)",),
        "company",
        None,
    ),
    "crediting_period_years": (
        (r"crediting period(?:\s+of)?\s*[:\-–]?\s*(\d{1,2})\s*years?",),
        "integer",
        "years",
    ),
    "crediting_period_start": (
        (
            r"(?:start date of crediting period|crediting period start(?: date)?)"
            r"\s*[:\-–]?\s*([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}|"
            r"\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4})(?![\d/-])",
        ),
        "date",
        None,
    ),
    "crediting_period_end": (
        (
            r"(?:end date of crediting period|crediting period end(?: date)?)"
            r"\s*[:\-–]?\s*([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}|"
            r"\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4})(?![\d/-])",
        ),
        "date",
        None,
    ),
    "country": ((r"(?:host country|project country|country)\s*[:\-]\s*([^\n\r]+)",), "text", None),
    "validator_name": ((r"(?:validator|validation body)\s*[:\-]\s*([^\n\r]+)",), "text", None),
    "verifier_name": (
        (r"(?:verifier|verification body|\bvvb)\s*[:\-]\s*([^\n\r]+)",),
        "text",
        None,
    ),
    "methodology_name": (
        tuple(
            rf"\b({re.escape(m)})\b"
            for m in ("ACM0002", "AMS-I.D", "AMS-I.F", "ACM0006", "AMS-I.A")
        ),
        "text",
        None,
    ),
    "grid_connection_status": ((r"(grid[- ]connected)",), "keyword", None),
    "installed_capacity_mw": ((r"(\d+(?:\.\d+)?)\s*MW",), "number", "MW"),
    "er_reported_tco2e": (
        (r"(?:ER|Emission Reductions?)\s*[:=]?\s*([\d,]+(?:\.\d+)?)",),
        "number",
        None,
    ),
    "be_value_tco2e": (
        (r"(?:BE|Baseline Emissions?)\s*[:=]?\s*([\d,]+(?:\.\d+)?)",),
        "number",
        None,
    ),
    "pe_value_tco2e": (
        (r"(?:PE|Project Emissions?)\s*[:=]?\s*([\d,]+(?:\.\d+)?)",),
        "number",
        None,
    ),
    "le_value_tco2e": ((r"(?:LE|Leakage)\s*[:=]?\s*([\d,]+(?:\.\d+)?)",), "number", None),
}


def extract_regex(
    parsed: ParsedDocument,
    project_id: str,
    registry: Registry,
    *,
    pipeline_run_id: UUID,
    page_numbers: tuple[int, ...] | None = None,
) -> ProjectExtraction:
    pages = parsed.pages
    if page_numbers is not None:
        if (
            not page_numbers
            or len(set(page_numbers)) != len(page_numbers)
            or any(
                type(number) is not int or not 1 <= number <= len(pages) for number in page_numbers
            )
        ):
            raise ValueError("select unique existing page numbers")
        pages = tuple(pages[number - 1] for number in sorted(page_numbers))
    observations = []
    for field_name in get_args(FieldName):
        candidates = []
        seen = set()
        if field_name in RULES:
            patterns, kind, unit = RULES[field_name]
            for pattern in patterns:
                for page in pages:
                    for match in re.finditer(pattern, page.text, flags=re.I):
                        raw = match.group(1)
                        normalized = re.sub(r"\s+", " ", raw).strip()
                        if kind == "text":
                            if (
                                "http://" in normalized
                                or "https://" in normalized
                                or "risk?" in normalized.lower()
                                or len(re.findall(r"[A-Za-z\u4e00-\u9fff]", normalized)) < 3
                            ):
                                continue
                            normalized = normalized[:120]
                        elif kind == "title":
                            if (
                                not 2 <= len(normalized) <= 240
                                or len(normalized.split()) > 12
                                or re.search(
                                    r"\b(?:considered|analysis|common practice|"
                                    r"shall|therefore|because)\b",
                                    normalized,
                                    re.I,
                                )
                            ):
                                continue
                        elif kind == "company":
                            if not 2 <= len(normalized) <= 180:
                                continue
                        elif kind == "integer":
                            normalized = int(raw)
                        elif kind == "number":
                            try:
                                normalized = float(raw.replace(",", ""))
                            except ValueError:
                                continue
                        elif kind == "keyword":
                            normalized = "grid-connected"
                        key = (page.page_number, match.start(1), match.end(1))
                        if key in seen:
                            continue
                        seen.add(key)
                        start = max(0, match.start() - 120)
                        end = min(len(page.text), match.end() + 120)
                        issues = ()
                        # ponytail: broad legacy rules; domain-aware extraction after comparison.
                        if kind == "number":
                            issues = ("broad_numeric_rule",)
                            if unit is None:
                                issues += ("unit_not_verified",)
                        elif kind == "keyword":
                            issues = ("keyword_presence_not_business_status",)
                        elif kind == "date":
                            issues = ("date_not_validated",)
                            if re.fullmatch(r"\d{4}", normalized):
                                issues += ("year_only_date",)
                            elif re.fullmatch(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", normalized):
                                issues += ("ambiguous_numeric_date",)
                        elif kind == "company":
                            issues = ("company_entity_not_resolved",)
                        candidates.append(
                            FieldObservation(
                                field_name=field_name,
                                raw_value=raw,
                                normalized_value=normalized,
                                unit=unit,
                                issues=issues,
                                evidence=(
                                    EvidenceRef(
                                        document_version_id=parsed.document_version_id,
                                        page_number=page.page_number,
                                        quote=page.text[start:end],
                                        char_start=start,
                                        char_end=end,
                                    ),
                                ),
                            )
                        )
        observations.extend(
            candidates
            or [
                FieldObservation(
                    field_name=field_name,
                    missing_reason="not_found"
                    if field_name in RULES
                    else "unsupported_by_baseline",
                )
            ]
        )
    return ProjectExtraction(
        project_id=project_id,
        registry=registry,
        document_version_id=parsed.document_version_id,
        parsed_document_id=parsed.parsed_document_id,
        extractor_name="regex",
        extractor_version="teacher-final-page-regex-v2",
        pipeline_run_id=pipeline_run_id,
        created_at=datetime.now(UTC),
        observations=tuple(observations),
    )
