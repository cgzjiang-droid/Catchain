"""Read-only review queue projections and deterministic human-review metrics."""

import hashlib
import json
import os
from collections import Counter
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from sqlalchemy import select
from sqlalchemy.engine import Engine

from catchain.domain import Registry
from catchain.domain.evidence import EvidenceRef
from catchain.domain.review_queue import ReviewMetricsSnapshot, ReviewQueueItem, ReviewQueueSnapshot
from catchain.storage.database import (
    candidate_evidence,
    canonical_heads,
    fact_candidates,
    processing_runs,
    review_decisions,
    validation_reports,
)

_CRITICAL_CODES = {
    "candidate_conflict",
    "evidence_page_invalid",
    "evidence_quote_missing",
    "evidence_version_invalid",
    "evidence_offsets_invalid",
    "field_type_invalid",
    "numeric_range_invalid",
}
_HIGH_PREFIXES = ("date_", "evidence_offsets_", "numeric_", "unit_", "field_type_")
_NORMAL_CODES = {
    "confidence_below_threshold",
    "confidence_unknown",
    "field_contract_pending",
    "semantic_support_pending",
    "ambiguous_abstention",
}


def _priority(status: str, issue_codes: Iterable[str]) -> tuple[str, int, tuple[str, ...]]:
    codes = tuple(dict.fromkeys(issue_codes))
    reasons: list[str] = []
    if status == "rejected":
        reasons.append("mechanical_rejection")
    if status == "missing":
        reasons.append("missing_candidate_value")
    if any(code in _CRITICAL_CODES for code in codes):
        reasons.append("critical_validation_issue")
    if any(code.startswith(_HIGH_PREFIXES) for code in codes):
        reasons.append("high_risk_validation_issue")
    if any(code in _NORMAL_CODES for code in codes):
        reasons.append("human_semantic_review")
    if not reasons:
        reasons.append("manual_review_required")
    if (
        "critical_validation_issue" in reasons
        or "mechanical_rejection" in reasons
        or "missing_candidate_value" in reasons
    ):
        return "critical", 100, tuple(reasons)
    if "high_risk_validation_issue" in reasons:
        return "high", 70, tuple(reasons)
    if "human_semantic_review" in reasons:
        return "normal", 40, tuple(reasons)
    return "low", 20, tuple(reasons)


def _json_value(raw: str):
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return raw


def _latest_decisions(connection, candidate_id: str) -> list[dict]:
    return (
        connection.execute(
            select(review_decisions)
            .where(review_decisions.c.candidate_id == candidate_id)
            .order_by(review_decisions.c.created_at.desc())
        )
        .mappings()
        .all()
    )


def _item_from_row(connection, row: dict, include_approved: bool) -> ReviewQueueItem | None:
    decisions = _latest_decisions(connection, row["candidate_id"])
    latest = decisions[0] if decisions else None
    review_state = latest["status"] if latest else "pending"
    if review_state == "approved" and not include_approved:
        return None
    issues = tuple(json.loads(row["issues_json"]))
    issue_codes = tuple(issue["code"] for issue in issues)
    priority, priority_score, priority_reasons = _priority(row["validation_status"], issue_codes)
    evidence_rows = (
        connection.execute(
            select(candidate_evidence)
            .where(candidate_evidence.c.candidate_id == row["candidate_id"])
            .order_by(candidate_evidence.c.evidence_index)
        )
        .mappings()
        .all()
    )
    evidence = tuple(
        EvidenceRef(
            document_version_id=ref["document_version_id"],
            page_number=ref["page_number"],
            quote=ref["quote"],
            char_start=ref["char_start"],
            char_end=ref["char_end"],
        )
        for ref in evidence_rows
    )
    current_fact_id = connection.execute(
        select(canonical_heads.c.fact_id).where(
            canonical_heads.c.registry == row["registry"],
            canonical_heads.c.project_id == row["project_id"],
            canonical_heads.c.field_name == row["field_name"],
        )
    ).scalar_one_or_none()
    return ReviewQueueItem(
        candidate_id=row["candidate_id"],
        validation_run_id=row["validation_run_id"],
        registry=Registry(row["registry"]),
        project_id=row["project_id"],
        field_name=row["field_name"],
        validation_status=row["validation_status"],
        review_state=review_state,
        priority=priority,
        priority_score=priority_score,
        priority_reasons=priority_reasons,
        value=_json_value(row["value_json"]),
        unit=row["unit"],
        issue_codes=issue_codes,
        issues=issues,
        evidence=evidence,
        evidence_count=len(evidence),
        current_fact_id=current_fact_id,
        decision_count=len(decisions),
        latest_decision_at=latest["created_at"] if latest else None,
    )


def _candidate_rows(connection, project_id: str | None = None, field_name: str | None = None):
    statement = select(
        fact_candidates, validation_reports.c.registry, validation_reports.c.project_id
    ).join(
        validation_reports,
        validation_reports.c.pipeline_run_id == fact_candidates.c.validation_run_id,
    )
    if project_id is not None:
        statement = statement.where(validation_reports.c.project_id == project_id)
    if field_name is not None:
        statement = statement.where(fact_candidates.c.field_name == field_name)
    return (
        connection.execute(statement.order_by(fact_candidates.c.observation_index))
        .mappings()
        .all()
    )


def build_review_queue(
    engine: Engine,
    *,
    project_id: str | None = None,
    field_name: str | None = None,
    include_approved: bool = False,
    limit: int | None = None,
) -> ReviewQueueSnapshot:
    if limit is not None and limit < 1:
        raise ValueError("limit must be positive")
    with engine.connect() as connection:
        items = [
            item
            for row in _candidate_rows(connection, project_id=project_id, field_name=field_name)
            if (item := _item_from_row(connection, row, include_approved)) is not None
        ]
    items.sort(key=lambda item: (-item.priority_score, item.project_id, item.field_name))
    if limit is not None:
        items = items[:limit]
    return ReviewQueueSnapshot(
        generated_at=datetime.now(UTC),
        project_id=project_id,
        field_name=field_name,
        include_approved=include_approved,
        items=tuple(items),
        counts_by_review_state=dict(Counter(item.review_state for item in items)),
        counts_by_priority=dict(Counter(item.priority for item in items)),
    )


def build_review_metrics(engine: Engine) -> ReviewMetricsSnapshot:
    with engine.connect() as connection:
        rows = _candidate_rows(connection)
        decisions = connection.execute(select(review_decisions)).mappings().all()
        evidence_counts = {
            row["candidate_id"]: connection.execute(
                select(candidate_evidence.c.candidate_id)
                .where(candidate_evidence.c.candidate_id == row["candidate_id"])
            ).first()
            is not None
            for row in rows
        }
        by_candidate = Counter(decision["candidate_id"] for decision in decisions)
        field_by_candidate = {row["candidate_id"]: row["field_name"] for row in rows}
        latest_state = {}
        for row in rows:
            candidate_decisions = _latest_decisions(connection, row["candidate_id"])
            latest_state[row["candidate_id"]] = (
                candidate_decisions[0]["status"] if candidate_decisions else "pending"
            )
        latencies = []
        for decision in decisions:
            candidate_run_id = next(
                (
                    row["validation_run_id"]
                    for row in rows
                    if row["candidate_id"] == decision["candidate_id"]
                ),
                None,
            )
            if candidate_run_id is None:
                continue
            run_payload = connection.execute(
                select(processing_runs.c.payload_json).where(
                    processing_runs.c.pipeline_run_id == candidate_run_id
                )
            ).scalar_one_or_none()
            if run_payload is None:
                continue
            try:
                finished_at = datetime.fromisoformat(json.loads(run_payload)["finished_at"])
                decided_at = datetime.fromisoformat(decision["created_at"])
            except (KeyError, TypeError, ValueError):
                continue
            latency = (decided_at - finished_at).total_seconds()
            if latency >= 0:
                latencies.append(latency)
    candidates_by_status = Counter(row["validation_status"] for row in rows)
    decisions_by_status = Counter(decision["status"] for decision in decisions)
    decision_count = len(decisions)
    return ReviewMetricsSnapshot(
        generated_at=datetime.now(UTC),
        total_candidates=len(rows),
        candidates_by_validation_status=dict(candidates_by_status),
        reviewed_candidates=sum(count > 0 for count in by_candidate.values()),
        pending_candidates=sum(
            state in {"pending", "unresolved", "rejected"} for state in latest_state.values()
        ),
        decisions=decision_count,
        decisions_by_status=dict(decisions_by_status),
        approval_rate=(
            decisions_by_status["approved"] / decision_count if decision_count else None
        ),
        unresolved_rate=(
            decisions_by_status["unresolved"] / decision_count if decision_count else None
        ),
        evidence_coverage=(sum(evidence_counts.values()) / len(rows) if rows else None),
        field_coverage=(
            len({field_by_candidate[candidate_id] for candidate_id in by_candidate})
            / len({row["field_name"] for row in rows})
            if rows
            else None
        ),
        rework_candidate_count=sum(count > 1 for count in by_candidate.values()),
        average_review_latency_seconds=(sum(latencies) / len(latencies) if latencies else None),
    )


def write_snapshot(output_dir: Path, prefix: str, snapshot) -> tuple[Path, bool]:
    """Write a content-addressed snapshot without overwriting an existing artifact."""
    stable = snapshot.model_dump(mode="json")
    stable.pop("generated_at", None)
    digest = hashlib.sha256(
        json.dumps(stable, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    path = output_dir / f"{prefix}-{digest}.json"
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        existing_stable = existing["snapshot"].copy()
        existing_stable.pop("generated_at", None)
        if existing_stable != stable:
            raise ValueError(f"snapshot artifact conflict: {path}")
        return path, True
    output_dir.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=output_dir, delete=False) as staged:
        temporary = Path(staged.name)
        try:
            json.dump(
                {"snapshot": snapshot.model_dump(mode="json")},
                staged,
                ensure_ascii=False,
                indent=2,
            )
            staged.flush()
            os.fsync(staged.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.link(temporary, path)
    except FileExistsError:
        return write_snapshot(output_dir, prefix, snapshot)
    finally:
        temporary.unlink(missing_ok=True)
    return path, False

