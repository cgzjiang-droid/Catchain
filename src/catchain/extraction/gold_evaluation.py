"""Compare an extraction with frozen human labels without guessing tolerances."""

import json
from typing import Literal

from catchain.domain import GoldDataset, GoldSample, ProjectExtraction


def _value_key(value, unit):
    return json.dumps([value, unit], ensure_ascii=False, sort_keys=True)


def evaluate_against_gold(gold: GoldSample, extraction: ProjectExtraction) -> dict:
    """Return field-level agreement metrics for one frozen sample."""

    if gold.status != "frozen":
        raise ValueError("only frozen GoldSample can produce accuracy")
    if (
        gold.project_id != extraction.project_id
        or gold.registry != extraction.registry
        or gold.document_version_id != extraction.document_version_id
        or gold.parsed_document_id != extraction.parsed_document_id
    ):
        raise ValueError("GoldSample and extraction identity differ")
    observations = {}
    for observation in extraction.observations:
        observations.setdefault(observation.field_name, []).append(observation)
    rows = []
    for label in gold.labels:
        candidates = observations.get(label.field_name, [])
        valued = [item for item in candidates if item.missing_reason is None]
        missing = [item for item in candidates if item.missing_reason is not None]
        if label.status == "unknown":
            outcome = "correct_abstention" if not valued else "unsupported_value"
        elif len(valued) > 1:
            outcome = "conflicting_candidates"
        elif not valued:
            outcome = "missing_or_abstained"
        elif _value_key(valued[0].normalized_value, valued[0].unit) == _value_key(
            label.value, label.unit
        ):
            outcome = "exact_match"
        else:
            outcome = "value_mismatch"
        rows.append(
            {
                "field_name": label.field_name,
                "gold_status": label.status,
                "outcome": outcome,
                "candidate_count": len(candidates),
                "evidence_present": any(item.evidence for item in valued),
                "candidate_missing_count": len(missing),
            }
        )
    agreements = sum(row["outcome"] in {"exact_match", "correct_abstention"} for row in rows)
    confirmed = [row for row in rows if row["gold_status"] == "confirmed"]
    unknown = [row for row in rows if row["gold_status"] == "unknown"]
    return {
        "schema_version": "1.0.0",
        "sample_id": gold.sample_id,
        "dataset_version": gold.dataset_version,
        "split": gold.split,
        "extractor_name": extraction.extractor_name,
        "extractor_version": extraction.extractor_version,
        "gold_status": gold.status,
        "rows": rows,
        "metrics": {
            "evaluated_fields": len(rows),
            "agreement_count": agreements,
            "accuracy": agreements / len(rows) if rows else None,
            "confirmed_fields": len(confirmed),
            "confirmed_accuracy": (
                sum(row["outcome"] == "exact_match" for row in confirmed) / len(confirmed)
                if confirmed
                else None
            ),
            "unknown_fields": len(unknown),
            "unknown_abstention_rate": (
                sum(row["outcome"] == "correct_abstention" for row in unknown) / len(unknown)
                if unknown
                else None
            ),
            "evidence_coverage": (
                sum(row["evidence_present"] for row in rows) / len(rows) if rows else None
            ),
        },
        "limitations": [
            "exact_value_and_unit_comparison",
            "no_unconfirmed_numeric_tolerance",
            "evidence_presence_not_quote_revalidation",
            "one_sample_summary_not_a_production_quality_claim",
        ],
    }


def aggregate_gold_evaluations(
    dataset: GoldDataset,
    reports: tuple[dict, ...],
    split: Literal["development", "validation", "test"] | None = None,
) -> dict:
    """Aggregate complete per-sample reports for one frozen dataset or split."""

    if dataset.status != "frozen":
        raise ValueError("only frozen GoldDataset can produce aggregate accuracy")
    selected = [sample for sample in dataset.samples if split is None or sample.split == split]
    expected_ids = {sample.sample_id for sample in selected}
    by_id = {report.get("sample_id"): report for report in reports}
    if len(by_id) != len(reports):
        raise ValueError("duplicate or missing sample_id in evaluation reports")
    if set(by_id) != expected_ids:
        raise ValueError("evaluation reports do not exactly cover the selected Gold split")
    rows = [by_id[sample_id] for sample_id in sorted(expected_ids)]
    if any(
        report.get("dataset_version") != dataset.dataset_version
        or report.get("gold_status") != "frozen"
        for report in rows
    ):
        raise ValueError("evaluation report dataset identity or status differs")
    all_metric_rows = [row for report in rows for row in report.get("rows", [])]
    agreement = sum(
        row.get("outcome") in {"exact_match", "correct_abstention"} for row in all_metric_rows
    )
    confirmed = [row for row in all_metric_rows if row.get("gold_status") == "confirmed"]
    unknown = [row for row in all_metric_rows if row.get("gold_status") == "unknown"]
    return {
        "schema_version": "1.0.0",
        "dataset_version": dataset.dataset_version,
        "split": split or "all",
        "gold_status": dataset.status,
        "sample_ids": sorted(expected_ids),
        "metrics": {
            "samples_evaluated": len(rows),
            "evaluated_fields": len(all_metric_rows),
            "agreement_count": agreement,
            "accuracy": agreement / len(all_metric_rows) if all_metric_rows else None,
            "confirmed_fields": len(confirmed),
            "confirmed_accuracy": (
                sum(row.get("outcome") == "exact_match" for row in confirmed) / len(confirmed)
                if confirmed
                else None
            ),
            "unknown_fields": len(unknown),
            "unknown_abstention_rate": (
                sum(row.get("outcome") == "correct_abstention" for row in unknown) / len(unknown)
                if unknown
                else None
            ),
        },
        "limitations": [
            "aggregate_requires_complete_selected_split",
            "exact_value_and_unit_comparison",
            "no_unconfirmed_numeric_tolerance",
            "evidence_presence_not_quote_revalidation",
        ],
    }
