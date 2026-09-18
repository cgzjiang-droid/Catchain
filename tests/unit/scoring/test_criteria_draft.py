import json
from importlib.resources import files


def test_criteria_have_unique_ids_and_do_not_imply_automatic_scores():
    draft = json.loads(
        files("catchain.scoring").joinpath("acm0002-quality-rubric-draft-v2.json").read_bytes()
    )
    criteria = [c for d in draft["dimensions"] for c in d["criteria"]]
    assert len(criteria) == 36
    assert len({c["criterion_id"] for c in criteria}) == 36
    assert draft["status"] == "draft_not_executable"
    assert draft["aggregation_policy"] == "manual_dimension_judgment_no_automatic_sum"
    for d in draft["dimensions"]:
        assert d["weight"] is None
        for c in d["criteria"]:
            assert c["criterion_id"].startswith(d["dimension_id"] + ".")
            assert "semantic_support" in c["human_checks"]
            assert "evidence" in c["required_output"]
