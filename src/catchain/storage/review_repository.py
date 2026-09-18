"""Single-machine human review with immutable history and stale-write protection."""

import json
from datetime import UTC, date, datetime
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy import insert, select, update

from catchain.domain import ProjectExtraction
from catchain.domain.review import ReviewRequest
from catchain.domain.validation import ExtractionValidationReport
from catchain.storage.database import (
    canonical_fact_sources,
    canonical_facts,
    canonical_heads,
    fact_candidates,
    review_decisions,
    review_requests,
    validation_reports,
)
from catchain.storage.document_repository import SqlAlchemyDocumentRepository
from catchain.validation.extraction import validate_extraction


class ReviewBlocked(ValueError):
    def __init__(self, codes):
        self.codes = sorted(codes)
        super().__init__(", ".join(self.codes))


def decide(engine, request: ReviewRequest):
    request = ReviewRequest.model_validate_json(request.model_dump_json())
    payload = request.model_dump_json()
    decision_id = str(request.decision_id)
    with engine.connect() as connection:
        # ponytail: SQLite writer lock; move to row locks if concurrent reviewers outgrow MVP.
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            existing = connection.execute(
                select(review_requests.c.payload_json).where(
                    review_requests.c.decision_id == decision_id
                )
            ).scalar_one_or_none()
            if existing is not None:
                if existing != payload:
                    raise ReviewBlocked(["decision_id_conflict"])
                fact_id = connection.execute(
                    select(canonical_facts.c.fact_id).where(
                        canonical_facts.c.decision_id == decision_id
                    )
                ).scalar_one_or_none()
                connection.commit()
                return {"status": "reused", "fact_id": fact_id, "canonical_writes": 0}
            candidate = (
                connection.execute(
                    select(fact_candidates).where(
                        fact_candidates.c.candidate_id == str(request.candidate_id)
                    )
                )
                .mappings()
                .one_or_none()
            )
            if candidate is None:
                raise ReviewBlocked(["candidate_not_found"])
            row = (
                connection.execute(
                    select(validation_reports).where(
                        validation_reports.c.pipeline_run_id == candidate["validation_run_id"]
                    )
                )
                .mappings()
                .one()
            )
            scope = {
                "registry": row["registry"],
                "project_id": row["project_id"],
                "field_name": candidate["field_name"],
            }
            predicate = (
                (canonical_heads.c.registry == scope["registry"])
                & (canonical_heads.c.project_id == scope["project_id"])
                & (canonical_heads.c.field_name == scope["field_name"])
            )
            current = connection.execute(
                select(canonical_heads.c.fact_id).where(predicate)
            ).scalar_one_or_none()
            expected = (
                str(request.expected_current_fact_id) if request.expected_current_fact_id else None
            )
            if current != expected:
                raise ReviewBlocked(["stale_current_fact"])
            before = (
                connection.execute(
                    select(canonical_facts.c.value_json).where(canonical_facts.c.fact_id == current)
                ).scalar_one_or_none()
                if current
                else "null"
            )
            fact_id = None
            source_link = None
            if request.status == "approved":
                if request.after.field_name != candidate["field_name"]:
                    raise ReviewBlocked(["replacement_field_mismatch"])
                original = ProjectExtraction.model_validate_json(row["extraction_json"])
                report = ExtractionValidationReport.model_validate_json(row["payload_json"])
                parsed = SqlAlchemyDocumentRepository(engine).get_parsed(report.parsed_document_id)
                if parsed is None:
                    raise ReviewBlocked(["parsed_document_absent"])
                revised = original.model_copy(update={"observations": (request.after,)})
                check = validate_extraction(parsed, revised, pipeline_run_id=uuid4()).checks[0]
                allowed = {
                    "semantic_support_pending",
                    "confidence_unknown",
                    "confidence_below_threshold",
                }
                blocked = {i.code for i in check.issues if i.code not in allowed}
                if blocked:
                    raise ReviewBlocked(blocked)
                for start, end in (("crediting_period_start", "crediting_period_end"),):
                    field = candidate["field_name"]
                    if field not in (start, end):
                        continue
                    counterpart = end if field == start else start
                    other = connection.execute(
                        select(canonical_facts.c.value_json)
                        .join(
                            canonical_heads, canonical_heads.c.fact_id == canonical_facts.c.fact_id
                        )
                        .where(
                            canonical_heads.c.registry == scope["registry"],
                            canonical_heads.c.project_id == scope["project_id"],
                            canonical_heads.c.field_name == counterpart,
                        )
                    ).scalar_one_or_none()
                    if other is not None:
                        values = (
                            (request.after.normalized_value, json.loads(other))
                            if field == start
                            else (json.loads(other), request.after.normalized_value)
                        )
                        if date.fromisoformat(values[0]) > date.fromisoformat(values[1]):
                            raise ReviewBlocked(["date_order_reversed"])
                fact_id = str(uuid5(NAMESPACE_URL, f"catchain:decision:{decision_id}"))
                source_link = {
                    "fact_id": fact_id,
                    "document_version_id": str(original.document_version_id),
                    "parsed_document_id": str(report.parsed_document_id),
                    "validation_run_id": str(candidate["validation_run_id"]),
                    "created_at": datetime.now(UTC).isoformat(),
                }
            after = (
                json.dumps(request.after.normalized_value, ensure_ascii=False)
                if request.after
                else "null"
            )
            connection.execute(
                insert(review_decisions).values(
                    decision_id=decision_id,
                    candidate_id=str(request.candidate_id),
                    reviewer=request.reviewer,
                    reason=request.reason,
                    status=request.status,
                    before_value_json=before,
                    after_value_json=after,
                    created_at=datetime.now(UTC).isoformat(),
                )
            )
            connection.execute(
                insert(review_requests).values(decision_id=decision_id, payload_json=payload)
            )
            if fact_id:
                connection.execute(
                    insert(canonical_facts).values(
                        fact_id=fact_id,
                        decision_id=decision_id,
                        **scope,
                        value_json=after,
                        unit=request.after.unit,
                    )
                )
                connection.execute(insert(canonical_fact_sources).values(**source_link))
                if current:
                    connection.execute(
                        update(canonical_heads).where(predicate).values(fact_id=fact_id)
                    )
                else:
                    connection.execute(insert(canonical_heads).values(**scope, fact_id=fact_id))
            connection.commit()
            return {
                "status": request.status,
                "fact_id": fact_id,
                "canonical_writes": int(fact_id is not None),
            }
        except Exception:
            connection.rollback()
            raise
