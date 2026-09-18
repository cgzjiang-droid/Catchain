from datetime import date

import pytest
from pydantic import ValidationError

from catchain.domain.policy import DimensionWeight, ScoringPolicy


def _dimensions(weight=None):
    return tuple(DimensionWeight(dimension_id=f"D{i:02d}", weight=weight) for i in range(1, 13))


def test_draft_policy_can_preserve_unconfirmed_weights():
    policy = ScoringPolicy(
        policy_version="acm0002-internal-draft-v1",
        rubric_version="acm0002-quality-rubric-draft-v2",
        dimensions=_dimensions(),
    )
    assert policy.status == "draft"


def test_approved_policy_requires_complete_weighted_authority():
    with pytest.raises(ValidationError, match="every dimension weight"):
        ScoringPolicy(
            policy_version="policy-v1",
            rubric_version="rubric-v1",
            status="approved",
            dimensions=_dimensions(),
            authority_sources=("https://example.org/rules",),
            approved_by="lead",
            approved_on=date(2026, 9, 18),
        )
    with pytest.raises(ValidationError, match="sum to 1"):
        ScoringPolicy(
            policy_version="policy-v1",
            rubric_version="rubric-v1",
            status="approved",
            dimensions=_dimensions(0.1),
            authority_sources=("https://example.org/rules",),
            approved_by="lead",
            approved_on=date(2026, 9, 18),
        )
    policy = ScoringPolicy(
        policy_version="policy-v1",
        rubric_version="rubric-v1",
        status="approved",
        dimensions=tuple(
            DimensionWeight(dimension_id=f"D{i:02d}", weight=1 / 12) for i in range(1, 13)
        ),
        authority_sources=("https://example.org/rules",),
        approved_by="lead",
        approved_on=date(2026, 9, 18),
    )
    assert policy.status == "approved"
