"""Fixed-input candidate differences, not a gold-label accuracy evaluation."""

import hashlib
import json
from uuid import NAMESPACE_URL, uuid5

from catchain.domain import ParsedDocument, PipelineRun, PipelineStage, ProjectExtraction, RunStatus
from catchain.extraction.baseline.regex import RULES, extract_regex
from catchain.extraction.llm.contract import select_pages


def compare_extraction(parsed: ParsedDocument, bundle: dict, started: dict) -> dict:
    llm = ProjectExtraction.model_validate(bundle["result"])
    run = PipelineRun.model_validate(bundle["run"])
    configuration = bundle["configuration"]
    fields = configuration["requested_fields"]
    pages = select_pages(parsed, tuple(started["selected_page_numbers"]))
    if (
        run.status is not RunStatus.SUCCEEDED
        or run.stage is not PipelineStage.LLM_EXTRACTED
        or run.pipeline_run_id != llm.pipeline_run_id
        or run.input_hash != hashlib.sha256(parsed.model_dump_json().encode()).hexdigest()
        or run.config_hash
        != hashlib.sha256(json.dumps(configuration, sort_keys=True).encode()).hexdigest()
        or llm.parsed_document_id != parsed.parsed_document_id
        or llm.document_version_id != parsed.document_version_id
        or started["run"]["pipeline_run_id"] != str(run.pipeline_run_id)
        or configuration != started["configuration"]
        or started["parsed_document_id"] != str(parsed.parsed_document_id)
        or started["document_version_id"] != str(parsed.document_version_id)
        or started["project_id"] != llm.project_id
        or started["registry"] != llm.registry.value
        or not fields
        or len(fields) != len(set(fields))
        or set(fields) != {observation.field_name for observation in llm.observations}
    ):
        raise ValueError("LLM artifact/input/run identity mismatch")
    texts = {page.page_number: page.text for page in pages}
    expected_hash = hashlib.sha256(
        json.dumps(
            [{"number": page.page_number, "text": page.text} for page in pages],
            sort_keys=True,
        ).encode()
    ).hexdigest()
    if expected_hash != configuration["selected_pages_hash"]:
        raise ValueError("selected pages hash differs")
    for observation in llm.observations:
        for evidence in observation.evidence:
            text = texts.get(evidence.page_number)
            if (
                text is None
                or evidence.char_start is None
                or evidence.char_end is None
                or evidence.char_end > len(text)
                or text[evidence.char_start : evidence.char_end] != evidence.quote
            ):
                raise ValueError("LLM evidence cannot be located in selected pages")
    rules_hash = hashlib.sha256(json.dumps(RULES, sort_keys=True).encode()).hexdigest()
    # A stable comparison identity; it does not pretend this is a historical model call.
    comparison_id = uuid5(NAMESPACE_URL, f"catchain:compare:{run.pipeline_run_id}:{rules_hash}")
    baseline = extract_regex(
        parsed,
        llm.project_id,
        llm.registry,
        pipeline_run_id=comparison_id,
        page_numbers=tuple(page.page_number for page in pages),
    )
    rows = []
    for field in fields:
        regex_items = [item for item in baseline.observations if item.field_name == field]
        llm_items = [item for item in llm.observations if item.field_name == field]

        def values(items):
            return {
                json.dumps([item.normalized_value, item.unit], ensure_ascii=False)
                for item in items
                if item.missing_reason is None
            }

        regex_values, llm_values = values(regex_items), values(llm_items)
        if not regex_values and not llm_values:
            outcome = "both_missing"
        elif not regex_values:
            outcome = "llm_only"
        elif not llm_values:
            outcome = "regex_only"
        else:
            outcome = "same_values" if regex_values == llm_values else "different_values"
        rows.append(
            {
                "field_name": field,
                "outcome": outcome,
                "regex_conflict": len(regex_values) > 1,
                "llm_conflict": len(llm_values) > 1,
                "regex": [item.model_dump(mode="json") for item in regex_items],
                "llm": [item.model_dump(mode="json") for item in llm_items],
            }
        )
    return {
        "comparison_id": str(comparison_id),
        "project_id": llm.project_id,
        "registry": llm.registry.value,
        "parsed_document_id": str(parsed.parsed_document_id),
        "document_version_id": str(parsed.document_version_id),
        "llm_pipeline_run_id": str(run.pipeline_run_id),
        "selected_page_numbers": [page.page_number for page in pages],
        "selected_pages_hash": expected_hash,
        "requested_fields": fields,
        "regex_version": baseline.extractor_version,
        "regex_rules_hash": rules_hash,
        "llm_version": llm.extractor_version,
        "rows": rows,
        "counts": {
            name: sum(row["outcome"] == name for row in rows)
            for name in (
                "both_missing",
                "llm_only",
                "regex_only",
                "same_values",
                "different_values",
            )
        },
        "accuracy": None,
        "gold_status": "not_available",
        "limitations": [
            "candidate_difference_not_accuracy",
            "selected_pages_only",
            "semantic_validation_pending",
            "exact_value_and_unit_comparison",
        ],
    }
