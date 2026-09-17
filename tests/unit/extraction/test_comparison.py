import copy
import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from catchain.domain import (
    ParsedDocument,
    ParsedPage,
    PipelineRun,
    PipelineStage,
    Registry,
    RunStatus,
)
from catchain.extraction.comparison import compare_extraction
from catchain.extraction.llm.contract import ground_response
from catchain.parsing.quality import measure_text_quality


def fixture():
    texts = (
        "Installed capacity: 5 MW",
        "Installed capacity: 12 MW\nInstalled capacity: 14 MW\nHost country: Chile",
        "Installed capacity: 99 MW",
    )
    now = datetime.now(UTC)
    parsed = ParsedDocument(
        document_version_id=uuid4(),
        parser_name="fixture",
        parser_version="1",
        created_at=now,
        pages=tuple(
            ParsedPage(
                page_number=i,
                text=text,
                char_start=0,
                char_end=len(text),
                quality=measure_text_quality(text),
            )
            for i, text in enumerate(texts, 1)
        ),
    )
    observations = [
        {
            "field_name": "installed_capacity_mw",
            "raw_value": f"{number} MW",
            "normalized_value": float(number),
            "unit": "MW",
            "missing_reason": None,
            "evidence": [{"page_number": 2, "quote": f"Installed capacity: {number} MW"}],
        }
        for number in (12, 14)
    ]
    observations += [
        {
            "field_name": "country",
            "raw_value": "Chile",
            "normalized_value": "Chile",
            "unit": None,
            "missing_reason": None,
            "evidence": [{"page_number": 2, "quote": "Host country: Chile"}],
        },
        {
            "field_name": "project_owner",
            "raw_value": None,
            "normalized_value": None,
            "unit": None,
            "missing_reason": "not_found",
            "evidence": [],
        },
    ]
    fields = ["installed_capacity_mw", "country", "project_owner"]
    run_id = uuid4()
    result = ground_response(
        json.dumps({"observations": observations}),
        parsed,
        selected_page_numbers=(2,),
        requested_fields=tuple(fields),
        project_id="VCS1",
        registry=Registry.VERRA,
        pipeline_run_id=run_id,
        extractor_name="fixture",
        extractor_version="1",
    )
    configuration = {
        "requested_fields": fields,
        "selected_pages_hash": hashlib.sha256(
            json.dumps([{"number": 2, "text": texts[1]}], sort_keys=True).encode()
        ).hexdigest(),
    }
    run = PipelineRun(
        pipeline_run_id=run_id,
        stage=PipelineStage.LLM_EXTRACTED,
        status=RunStatus.SUCCEEDED,
        input_hash=hashlib.sha256(parsed.model_dump_json().encode()).hexdigest(),
        config_hash=hashlib.sha256(json.dumps(configuration, sort_keys=True).encode()).hexdigest(),
        started_at=now,
        finished_at=datetime.now(UTC),
    )
    bundle = {
        "result": result.model_dump(mode="json"),
        "run": run.model_dump(mode="json"),
        "configuration": configuration,
    }
    started = {
        "run": run.model_dump(mode="json"),
        "configuration": configuration,
        "selected_page_numbers": [2],
        "project_id": "VCS1",
        "registry": "verra",
        "parsed_document_id": str(parsed.parsed_document_id),
        "document_version_id": str(parsed.document_version_id),
    }
    return parsed, bundle, started


def test_same_pages_preserve_original_numbers_conflicts_and_abstentions():
    parsed, bundle, started = fixture()
    report = compare_extraction(parsed, bundle, started)
    assert report["selected_page_numbers"] == [2]
    assert report["counts"]["same_values"] == 2 and report["counts"]["both_missing"] == 1
    capacity = report["rows"][0]
    assert capacity["regex_conflict"] and capacity["llm_conflict"]
    assert [item["normalized_value"] for item in capacity["regex"]] == [12.0, 14.0]
    assert all(item["evidence"][0]["page_number"] == 2 for item in capacity["regex"])
    assert report["accuracy"] is None
    assert compare_extraction(parsed, bundle, started) == report


@pytest.mark.parametrize("kind", ["page_scope", "evidence", "identity", "input_hash"])
def test_comparison_rejects_tampered_provenance(kind):
    parsed, bundle, started = fixture()
    bundle, started = copy.deepcopy(bundle), copy.deepcopy(started)
    if kind == "page_scope":
        started["selected_page_numbers"] = [1]
    elif kind == "evidence":
        bundle["result"]["observations"][0]["evidence"][0]["quote"] = "invented quote"
    elif kind == "identity":
        bundle["result"]["parsed_document_id"] = str(uuid4())
    else:
        bundle["run"]["input_hash"] = "b" * 64
    with pytest.raises(ValueError):
        compare_extraction(parsed, bundle, started)
