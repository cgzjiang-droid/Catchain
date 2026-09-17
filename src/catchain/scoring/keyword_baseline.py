"""Reproduce teacher-final keyword scoring over traceable page text."""

import hashlib
import json
import re
from importlib.resources import files

from catchain.domain import EvidenceRef, ParsedDocument


def _first_evidence(documents: tuple[ParsedDocument, ...], pattern: str) -> EvidenceRef | None:
    for document in documents:
        for page in document.pages:
            match = re.search(pattern, page.text, flags=re.I)
            if match:
                start = max(0, match.start() - 120)
                end = min(len(page.text), match.end() + 120)
                return EvidenceRef(
                    document_version_id=document.document_version_id,
                    page_number=page.page_number,
                    quote=page.text[start:end],
                    char_start=start,
                    char_end=end,
                )
    return None


def score_keywords(parsed_documents: tuple[ParsedDocument, ...]) -> dict:
    if not parsed_documents:
        raise ValueError("keyword scoring requires at least one Parsed document")
    raw_config = files("catchain.scoring").joinpath("teacher-final-keywords-v1.json").read_bytes()
    config = json.loads(raw_config)
    dimensions = []
    for rule in config["dimensions"]:
        counts = {}
        evidence = []
        for level in ("high", "mid"):
            counts[level] = 0
            for pattern in rule[f"keywords_{level}"]:
                hit = _first_evidence(parsed_documents, pattern)
                if hit is not None:
                    counts[level] += 1
                    if len(evidence) < 3:
                        evidence.append(hit.model_dump(mode="json"))
        high, mid = counts["high"], counts["mid"]
        # ponytail: keyword presence ignores negation; use validated facts for final assessment.
        score = 3 if high >= 3 else 2 if high >= 1 or mid >= 2 else 1 if mid >= 1 else 0
        dimensions.append(
            {
                "dimension_id": rule["id"],
                "dimension_name": rule["name"],
                "score": score,
                "hit_count_high": high,
                "hit_count_mid": mid,
                "evidence": evidence,
            }
        )
    total = sum(dimension["score"] for dimension in dimensions)
    return {
        "baseline_version": config["baseline_version"],
        "source_sha256": config["source_sha256"],
        "rules_sha256": hashlib.sha256(raw_config).hexdigest(),
        "input_documents": [
            {
                "parsed_document_id": str(document.parsed_document_id),
                "document_version_id": str(document.document_version_id),
            }
            for document in parsed_documents
        ],
        "dimensions": dimensions,
        "total_score": total,
        "max_score": 36,
        "keyword_score_ratio": total / 36,
        "limitations": ["keyword_presence_only", "no_cross_page_matches"],
    }
