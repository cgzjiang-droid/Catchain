"""Audit approved inputs against the legacy 12 dimensions, without inventing scores."""

import hashlib
import json
from importlib.resources import files

from sqlalchemy import select

from catchain.domain import ProjectExtraction, Registry
from catchain.domain.review import ReviewRequest
from catchain.domain.validation import ExtractionValidationReport
from catchain.storage.database import (
    canonical_facts,
    canonical_heads,
    document_versions,
    fact_candidates,
    parsed_documents,
    review_decisions,
    review_requests,
    source_documents,
    validation_reports,
)


def project_readiness(engine, *, registry: Registry, project_id: str) -> dict:
    if not project_id.strip():
        raise ValueError("project_id cannot be blank")
    raw = files("catchain.scoring").joinpath("acm0002-readiness-v1.json").read_bytes()
    policy = json.loads(raw)
    facts = {}
    statement = (
        select(
            canonical_facts,
            review_decisions.c.candidate_id,
            review_requests.c.payload_json.label("request_json"),
            validation_reports.c.payload_json.label("report_json"),
            validation_reports.c.extraction_json,
            document_versions.c.sha256,
            document_versions.c.source_document_id,
            source_documents.c.source_url,
        )
        .select_from(canonical_heads)
        .join(canonical_facts, canonical_heads.c.fact_id == canonical_facts.c.fact_id)
        .join(review_decisions, canonical_facts.c.decision_id == review_decisions.c.decision_id)
        .join(review_requests, review_decisions.c.decision_id == review_requests.c.decision_id)
        .join(fact_candidates, review_decisions.c.candidate_id == fact_candidates.c.candidate_id)
        .join(
            validation_reports,
            fact_candidates.c.validation_run_id == validation_reports.c.pipeline_run_id,
        )
        .join(
            parsed_documents,
            parsed_documents.c.parsed_document_id == validation_reports.c.parsed_document_id,
        )
        .join(
            document_versions,
            document_versions.c.document_version_id == parsed_documents.c.document_version_id,
        )
        .join(
            source_documents,
            document_versions.c.source_document_id == source_documents.c.source_document_id,
        )
        .where(
            canonical_heads.c.registry == registry.value, canonical_heads.c.project_id == project_id
        )
        .order_by(canonical_facts.c.field_name)
    )
    with engine.connect() as connection:
        for row in connection.execute(statement).mappings():
            request = ReviewRequest.model_validate_json(row["request_json"])
            report = ExtractionValidationReport.model_validate_json(row["report_json"])
            extraction = ProjectExtraction.model_validate_json(row["extraction_json"])
            after = request.after
            if (
                request.status != "approved"
                or after is None
                or after.field_name != row["field_name"]
                or str(request.decision_id) != row["decision_id"]
                or str(request.candidate_id) != row["candidate_id"]
                or json.loads(row["value_json"]) != after.normalized_value
                or row["unit"] != after.unit
                or (report.registry, report.project_id) != (registry, project_id)
            ):
                raise ValueError("canonical provenance mismatch")
            facts[row["field_name"]] = {
                "fact_id": row["fact_id"],
                "decision_id": row["decision_id"],
                "candidate_id": row["candidate_id"],
                "value": after.normalized_value,
                "unit": after.unit,
                "evidence": [e.model_dump(mode="json") for e in after.evidence],
                "parsed_document_id": str(report.parsed_document_id),
                "document_version_id": str(report.document_version_id),
                "source_document_id": row["source_document_id"],
                "source_url": row["source_url"],
                "sha256": row["sha256"],
                "extraction_run_id": str(report.extraction_run_id),
                "validation_run_id": str(report.pipeline_run_id),
                "extraction_method": extraction.extractor_name,
                "extractor_version": extraction.extractor_version,
                "review_policy": request.policy_version,
            }
    scope = facts.get("methodology_name", {}).get("value") == "ACM0002"
    dimensions = []
    for rule in policy["dimensions"]:
        available = [field for field in rule["input_fields"] if field in facts]
        missing = [field for field in rule["input_fields"] if field not in facts]
        dimensions.append(
            {
                "dimension_id": rule["dimension_id"],
                "name": rule["name"],
                "input_fields": rule["input_fields"],
                "available_fields": available,
                "missing_fields": missing,
                "fact_ids": [facts[f]["fact_id"] for f in available],
                "score": None,
                "weight": None,
                "status": "missing_inputs" if missing else "rubric_pending",
                "reason": "Approved field presence does not establish evidence sufficiency.",
            }
        )
    return {
        "schema_version": "1.0.0",
        "policy_version": policy["policy_version"],
        "rules_sha256": hashlib.sha256(raw).hexdigest(),
        "legacy_source_hashes": policy["source_hashes"],
        "registry": registry.value,
        "project_id": project_id,
        "methodology_scope": "confirmed_by_reviewed_fact"
        if scope
        else "unconfirmed_or_out_of_scope",
        "facts": facts,
        "dimensions": dimensions,
        "total_score": None,
        "weight_policy": "unconfirmed",
        "accuracy": None,
        "gold_status": "unavailable",
        "model_calls": 0,
        "limitations": [
            "readiness_only",
            "legacy_rubric_not_official_policy",
            "no_period_alignment_check",
            "no_evidence_sufficiency_judgment",
        ],
    }
