"""Atomic, immutable validation imports. No automatic canonical promotion."""

import hashlib
import json
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import insert, select
from sqlalchemy.engine import Engine

from catchain.domain import PipelineRun, PipelineStage, ProjectExtraction, RunStatus
from catchain.domain.validation import ExtractionValidationReport
from catchain.storage.database import (
    candidate_evidence,
    fact_candidates,
    processing_runs,
    validation_reports,
)
from catchain.storage.document_repository import SqlAlchemyDocumentRepository


class SqlAlchemyFactRepository:
    def __init__(self, engine: Engine):
        self.engine = engine

    def import_validation(
        self,
        report: ExtractionValidationReport,
        run: PipelineRun,
        extraction: ProjectExtraction,
        extraction_run: PipelineRun,
    ) -> bool:
        """Return True on exact reuse; reject changed payload for an existing run."""
        documents = SqlAlchemyDocumentRepository(self.engine)
        if (
            extraction.pipeline_run_id != report.extraction_run_id
            or extraction_run.pipeline_run_id != report.extraction_run_id
            or extraction_run.stage
            not in {PipelineStage.BASELINE_EXTRACTED, PipelineStage.LLM_EXTRACTED}
            or extraction_run.status != RunStatus.SUCCEEDED
            or extraction_run.input_hash != run.input_hash
            or extraction.parsed_document_id != report.parsed_document_id
            or extraction.document_version_id != report.document_version_id
            or (extraction.registry, extraction.project_id) != (report.registry, report.project_id)
            or extraction.observations != tuple(c.observation for c in report.checks)
        ):
            raise ValueError("original extraction/report mismatch")
        parsed = documents.get_parsed(report.parsed_document_id)
        version = documents.get_version(report.document_version_id)
        source = documents.get_source(version.source_document_id) if version else None
        if (
            parsed is None
            or source is None
            or parsed.document_version_id != report.document_version_id
            or (source.registry, source.registry_project_id) != (report.registry, report.project_id)
            or run.pipeline_run_id != report.pipeline_run_id
            or run.status != RunStatus.SUCCEEDED
            or run.stage != PipelineStage.QUALITY_VALIDATED
            or run.input_hash != hashlib.sha256(parsed.model_dump_json().encode()).hexdigest()
        ):
            raise ValueError("validation/source/run identity mismatch")
        # Even rejected evidence must point to this version; preserve its bad quote for audit.
        for check in report.checks:
            for ref in check.observation.evidence:
                if ref.document_version_id != report.document_version_id:
                    raise ValueError("evidence version mismatch")
                if check.status != "rejected":
                    page = next((p for p in parsed.pages if p.page_number == ref.page_number), None)
                    if page is None or not ref.quote.strip() or ref.quote not in page.text:
                        raise ValueError("evidence is not grounded")
                    if (
                        ref.char_start is not None
                        and ref.char_end is not None
                        and (
                            ref.char_end > len(page.text)
                            or page.text[ref.char_start : ref.char_end] != ref.quote
                        )
                    ):
                        raise ValueError("evidence offsets mismatch")
        report_json, run_json = report.model_dump_json(), run.model_dump_json()
        extraction_json = extraction.model_dump_json()
        run_id = str(run.pipeline_run_id)
        with self.engine.begin() as connection:
            existing = connection.execute(
                select(validation_reports.c.payload_json).where(
                    validation_reports.c.pipeline_run_id == run_id
                )
            ).scalar_one_or_none()
            if existing is not None:
                prior = connection.execute(
                    select(processing_runs.c.payload_json).where(
                        processing_runs.c.pipeline_run_id == run_id
                    )
                ).scalar_one()
                original = connection.execute(
                    select(validation_reports.c.extraction_json).where(
                        validation_reports.c.pipeline_run_id == run_id
                    )
                ).scalar_one()
                original_run = connection.execute(
                    select(processing_runs.c.payload_json).where(
                        processing_runs.c.pipeline_run_id == str(extraction_run.pipeline_run_id)
                    )
                ).scalar_one()
                if (
                    existing != report_json
                    or prior != run_json
                    or original != extraction_json
                    or original_run != extraction_run.model_dump_json()
                ):
                    raise ValueError("immutable validation run conflict")
                return True
            prior_extraction = connection.execute(
                select(processing_runs.c.payload_json).where(
                    processing_runs.c.pipeline_run_id == str(extraction_run.pipeline_run_id)
                )
            ).scalar_one_or_none()
            if prior_extraction is None:
                connection.execute(
                    insert(processing_runs).values(
                        pipeline_run_id=str(extraction_run.pipeline_run_id),
                        payload_json=extraction_run.model_dump_json(),
                    )
                )
            elif prior_extraction != extraction_run.model_dump_json():
                raise ValueError("immutable extraction run conflict")
            connection.execute(
                insert(processing_runs).values(pipeline_run_id=run_id, payload_json=run_json)
            )
            connection.execute(
                insert(validation_reports).values(
                    pipeline_run_id=run_id,
                    extraction_run_id=str(report.extraction_run_id),
                    extraction_json=extraction_json,
                    parsed_document_id=str(report.parsed_document_id),
                    registry=report.registry.value,
                    project_id=report.project_id,
                    payload_json=report_json,
                )
            )
            for check in report.checks:
                candidate_id = str(
                    uuid5(NAMESPACE_URL, f"catchain:{run_id}:{check.observation_index}")
                )
                observation = check.observation
                connection.execute(
                    insert(fact_candidates).values(
                        candidate_id=candidate_id,
                        validation_run_id=run_id,
                        observation_index=check.observation_index,
                        field_name=observation.field_name,
                        value_json=json.dumps(observation.normalized_value, ensure_ascii=False),
                        unit=observation.unit,
                        validation_status=check.status,
                        issues_json=json.dumps([i.model_dump(mode="json") for i in check.issues]),
                    )
                )
                for index, ref in enumerate(observation.evidence):
                    connection.execute(
                        insert(candidate_evidence).values(
                            candidate_id=candidate_id,
                            evidence_index=index,
                            document_version_id=str(ref.document_version_id),
                            page_number=ref.page_number,
                            quote=ref.quote,
                            char_start=ref.char_start,
                            char_end=ref.char_end,
                        )
                    )
        return False

    def get_validation(self, run_id) -> ExtractionValidationReport | None:
        with self.engine.connect() as connection:
            payload = connection.execute(
                select(validation_reports.c.payload_json).where(
                    validation_reports.c.pipeline_run_id == str(run_id)
                )
            ).scalar_one_or_none()
        return ExtractionValidationReport.model_validate_json(payload) if payload else None
