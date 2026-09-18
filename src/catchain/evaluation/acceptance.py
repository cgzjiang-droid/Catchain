"""Prevent official metrics until both policy and human Gold are frozen."""

from __future__ import annotations

from typing import Literal

from catchain.domain import GoldDataset
from catchain.domain.policy import ScoringPolicy
from catchain.extraction.gold_evaluation import aggregate_gold_evaluations


class AcceptanceBlocked(ValueError):
    """Raised when evaluation inputs are not eligible for production claims."""


def evaluate_frozen_gold(
    *,
    policy: ScoringPolicy,
    gold: GoldDataset,
    reports: tuple[dict, ...],
    split: Literal["development", "validation", "test"] = "test",
) -> dict:
    if policy.status != "approved":
        raise AcceptanceBlocked("approved scoring policy is required")
    if gold.status != "frozen":
        raise AcceptanceBlocked("frozen human Gold dataset is required")
    result = aggregate_gold_evaluations(gold, reports, split=split)
    rows = [row for report in reports for row in report.get("rows", [])]
    conflicts = sum(row.get("outcome") == "conflicting_candidates" for row in rows)
    result["metrics"]["conflict_rate"] = conflicts / len(rows) if rows else None
    result["policy_version"] = policy.policy_version
    result["policy_rubric_version"] = policy.rubric_version
    result["policy_status"] = policy.status
    return result

