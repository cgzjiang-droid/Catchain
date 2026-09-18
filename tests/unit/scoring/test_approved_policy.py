import json
from datetime import date

import pytest

from catchain.scoring.approved_policy_loader import PolicyBlocked, load_approved_policy


def policy(status: str) -> dict:
    return {
        "policy_version": "acm0002-approved-v1",
        "rubric_version": "acm0002-rubric-v1",
        "status": status,
        "dimensions": [
            {"dimension_id": f"D{i:02d}", "weight": 1 / 12} for i in range(1, 13)
        ],
        "authority_sources": ["https://example.org/policy"],
        "approved_by": "lead",
        "approved_on": date.today().isoformat(),
    }


def test_loader_rejects_draft_policy(tmp_path) -> None:
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(policy("draft")))

    with pytest.raises(PolicyBlocked, match="not approved"):
        load_approved_policy(path)


def test_loader_returns_hash_for_approved_policy(tmp_path) -> None:
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(policy("approved")))

    loaded = load_approved_policy(path)

    assert len(loaded.sha256) == 64
    assert loaded.policy.status == "approved"

