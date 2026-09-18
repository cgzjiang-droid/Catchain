"""Generate version-controlled JSON Schemas from CATchain domain models."""

import json
from pathlib import Path

from pydantic import BaseModel

from catchain.domain import (
    DocumentVersion,
    EvidenceRef,
    FieldObservation,
    ParsedDocument,
    PipelineRun,
    ProjectExtraction,
    SourceDocument,
)
from catchain.domain.assessment import AssessmentContext
from catchain.domain.consistency import ProjectConsistencyReport
from catchain.domain.evaluation import EvaluationResult
from catchain.domain.gold import GoldDataset, GoldSample
from catchain.domain.judgment import JudgmentRequest
from catchain.domain.policy import ScoringPolicy
from catchain.domain.production import ProductionChecklist
from catchain.domain.review import ReviewRequest
from catchain.domain.review_queue import ReviewMetricsSnapshot, ReviewQueueItem, ReviewQueueSnapshot
from catchain.domain.validation import ExtractionValidationReport

SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "evaluation-result": EvaluationResult,
    "gold-sample": GoldSample,
    "gold-dataset": GoldDataset,
    "scoring-policy": ScoringPolicy,
    "production-checklist": ProductionChecklist,
    "review-queue-item": ReviewQueueItem,
    "review-queue-snapshot": ReviewQueueSnapshot,
    "review-metrics-snapshot": ReviewMetricsSnapshot,
    "judgment-request": JudgmentRequest,
    "assessment-context": AssessmentContext,
    "review-request": ReviewRequest,
    "extraction-validation-report": ExtractionValidationReport,
    "document-version": DocumentVersion,
    "evidence-ref": EvidenceRef,
    "field-observation": FieldObservation,
    "parsed-document": ParsedDocument,
    "pipeline-run": PipelineRun,
    "project-extraction": ProjectExtraction,
    "project-consistency-report": ProjectConsistencyReport,
    "source-document": SourceDocument,
}


def generate_json_schemas(output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for schema_name, model_type in sorted(SCHEMA_MODELS.items()):
        output_path = output_dir / f"{schema_name}.schema.json"
        serialized = json.dumps(
            model_type.model_json_schema(),
            indent=2,
            sort_keys=True,
        )
        output_path.write_text(f"{serialized}\n", encoding="utf-8")
        written.append(output_path)

    return written
