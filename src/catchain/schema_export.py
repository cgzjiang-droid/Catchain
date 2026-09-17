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

SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "document-version": DocumentVersion,
    "evidence-ref": EvidenceRef,
    "field-observation": FieldObservation,
    "parsed-document": ParsedDocument,
    "pipeline-run": PipelineRun,
    "project-extraction": ProjectExtraction,
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
