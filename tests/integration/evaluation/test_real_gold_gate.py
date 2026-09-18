from datetime import date

import pytest

from catchain.domain import GoldDataset, GoldSample
from catchain.domain.policy import DimensionWeight, ScoringPolicy
from catchain.evaluation.acceptance import AcceptanceBlocked, evaluate_frozen_gold


def approved_policy() -> ScoringPolicy:
    return ScoringPolicy(
        policy_version="approved-v1",
        rubric_version="rubric-v1",
        status="approved",
        dimensions=tuple(
            DimensionWeight(dimension_id=f"D{i:02d}", weight=1 / 12) for i in range(1, 13)
        ),
        authority_sources=("https://example.org/policy",),
        approved_by="lead",
        approved_on=date.today(),
    )


def test_acceptance_rejects_unfrozen_gold() -> None:
    gold = GoldDataset(
        dataset_version="gold-v1",
        samples=(
            GoldSample(
                dataset_version="gold-v1",
                sample_id="sample-1",
                split="test",
                registry="verra",
                project_id="VCS-1",
                document_version_id="00000000-0000-0000-0000-000000000001",
                parsed_document_id="00000000-0000-0000-0000-000000000002",
                labels=(
                    {
                        "field_name": "project_name",
                        "status": "unknown",
                        "reason": "not established",
                    },
                ),
                reviewers=("r1", "r2"),
                status="draft",
            ),
        ),
    )

    with pytest.raises(AcceptanceBlocked, match="frozen"):
        evaluate_frozen_gold(policy=approved_policy(), gold=gold, reports=())

