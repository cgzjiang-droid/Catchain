import json
from importlib.resources import files


def test_rubric_draft_preserves_business_inputs_without_activating_scores():
    root = files("catchain.scoring")
    draft = json.loads(root.joinpath("acm0002-quality-rubric-draft-v1.json").read_bytes())
    baseline = json.loads(root.joinpath("acm0002-readiness-v1.json").read_bytes())
    assert draft["status"] == "draft_not_executable"
    assert draft["missing_policy"] == "unknown_not_zero"
    assert draft["weight_policy"] == "unconfirmed_no_total"
    assert len(draft["dimensions"]) == 12
    for rule, original in zip(draft["dimensions"], baseline["dimensions"], strict=True):
        assert rule["dimension_id"] == original["dimension_id"]
        assert rule["input_fields"] == original["input_fields"]
        assert rule["weight"] is None
        assert len(rule["evidence_requirements"]) >= 3
        assert set(rule["score_definitions"]) == {"0", "1", "2", "3"}
        assert "evidence" in rule["required_judgment_fields"]
