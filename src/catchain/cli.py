"""CATchain command-line interface."""

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Annotated
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import typer

from catchain.domain import (
    DocumentType,
    ParsedDocument,
    PipelineRun,
    PipelineStage,
    ProjectExtraction,
    Registry,
    RunStatus,
    SourceDocument,
)
from catchain.extraction.baseline.regex import RULES, extract_regex
from catchain.ingestion import RawBlobStore, ingest_local_document
from catchain.parsing import (
    OcrError,
    PdfParseError,
    RenderedPageInspector,
    TesseractOcrAdapter,
    TextQualityPolicy,
    parse_with_ocr_fallback,
)
from catchain.schema_export import generate_json_schemas
from catchain.scoring.keyword_baseline import score_keywords
from catchain.storage import SqlAlchemyDocumentRepository, create_schema, create_sqlite_engine
from catchain.storage.baseline_artifacts import ArtifactConflictError, store_baseline_artifact

app = typer.Typer(help="Traceable carbon document processing.")
schema_app = typer.Typer(help="Manage generated schemas.")
ingest_app = typer.Typer(help="Import source documents into the Raw layer.")
parse_app = typer.Typer(help="Convert Raw PDF versions into Parsed documents.")
extract_app = typer.Typer(help="Produce evidence-backed candidate artifacts.")
score_app = typer.Typer(help="Run comparison scoring baselines.")
dataset_app = typer.Typer(help="Build and sample large dataset manifests.")
production_app = typer.Typer(help="Check production readiness gates.")
compare_app = typer.Typer(help="Compare candidates on identical selected pages.")
evaluate_app = typer.Typer(help="Evaluate outputs against frozen human Gold labels.")
validate_app = typer.Typer(help="Check candidate types, evidence and review requirements.")
app.add_typer(schema_app, name="schema")
app.add_typer(ingest_app, name="ingest")
app.add_typer(parse_app, name="parse")
app.add_typer(extract_app, name="extract")
app.add_typer(score_app, name="score")
app.add_typer(dataset_app, name="dataset")
app.add_typer(production_app, name="production")
app.add_typer(compare_app, name="compare")
app.add_typer(evaluate_app, name="evaluate")
app.add_typer(validate_app, name="validate")
store_app = typer.Typer(help="Persist validated candidates without canonical promotion.")
app.add_typer(store_app, name="store")
review_app = typer.Typer(help="Record human decisions and explicitly approve grounded facts.")
app.add_typer(review_app, name="review")


@dataset_app.command("manifest")
def dataset_manifest_command(
    root: Annotated[Path, typer.Argument(exists=True, file_okay=False)],
    output: Annotated[Path, typer.Option("--output")] = Path("data/dataset-manifest.jsonl"),
    registry: Annotated[Registry | None, typer.Option("--registry")] = None,
    project_id: Annotated[str | None, typer.Option("--project-id")] = None,
    document_type: Annotated[DocumentType | None, typer.Option("--document-type")] = None,
    declared_version: Annotated[str | None, typer.Option("--declared-version")] = None,
) -> None:
    from catchain.dataset import build_manifest

    try:
        header = build_manifest(
            root,
            output,
            registry=registry,
            project_id=project_id,
            document_type=document_type,
            declared_version=declared_version,
        )
    except (OSError, ValueError):
        _fail_parse("DATASET_MANIFEST_FAILED", "dataset manifest generation failed")
    typer.echo(
        json.dumps(
            {"status": "stored", "manifest": str(output), **header.model_dump(mode="json")}
        )
    )


@dataset_app.command("sample")
def dataset_sample_command(
    manifest: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    output: Annotated[Path, typer.Option("--output")],
    development: Annotated[int, typer.Option("--development")] = 0,
    validation: Annotated[int, typer.Option("--validation")] = 0,
    test: Annotated[int, typer.Option("--test")] = 0,
    seed: Annotated[int, typer.Option("--seed")] = 0,
) -> None:
    from catchain.dataset import sample_manifest

    try:
        counts = sample_manifest(
            manifest,
            output,
            development=development,
            validation=validation,
            test=test,
            seed=seed,
        )
    except (OSError, ValueError):
        _fail_parse("DATASET_SAMPLE_FAILED", "dataset sampling failed")
    typer.echo(json.dumps({"status": "stored", "manifest": str(output), "counts": counts}))


@production_app.command("check")
def production_check_command(
    evidence_file: Annotated[Path | None, typer.Option("--evidence-file")] = None,
) -> None:
    from catchain.production import production_checklist

    try:
        evidence = (
            json.loads(evidence_file.read_text(encoding="utf-8")) if evidence_file else {}
        )
        result = production_checklist(evidence)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        _fail_parse("PRODUCTION_CHECK_FAILED", "production evidence file is invalid")
    typer.echo(result.model_dump_json())
    if result.status == "blocked":
        raise typer.Exit(code=2)


@review_app.command("queue")
def review_queue_command(
    project_id: Annotated[str | None, typer.Option("--project-id")] = None,
    field_name: Annotated[str | None, typer.Option("--field-name")] = None,
    include_approved: Annotated[bool, typer.Option("--include-approved")] = False,
    limit: Annotated[int | None, typer.Option("--limit")] = None,
    database: Annotated[Path, typer.Option("--database")] = Path("data/catchain.sqlite"),
    output_dir: Annotated[Path, typer.Option("--output-dir")] = Path("data/review/queue"),
) -> None:
    from catchain.review_queue import build_review_queue, write_snapshot

    try:
        if not database.is_file():
            raise ValueError("source database absent")
        snapshot = build_review_queue(
            create_sqlite_engine(database),
            project_id=project_id,
            field_name=field_name,
            include_approved=include_approved,
            limit=limit,
        )
        path, reused = write_snapshot(output_dir, "review-queue", snapshot)
    except (ValueError, OSError):
        _fail_parse("REVIEW_QUEUE_FAILED", "review queue query or artifact storage failed")
    typer.echo(
        json.dumps(
            {
                "status": "reused" if reused else "stored",
                "artifact_path": str(path),
                "item_count": len(snapshot.items),
                "counts_by_review_state": snapshot.counts_by_review_state,
                "counts_by_priority": snapshot.counts_by_priority,
            },
            ensure_ascii=False,
        )
    )


@review_app.command("metrics")
def review_metrics_command(
    database: Annotated[Path, typer.Option("--database")] = Path("data/catchain.sqlite"),
    output_dir: Annotated[Path, typer.Option("--output-dir")] = Path("data/review/metrics"),
) -> None:
    from catchain.review_queue import build_review_metrics, write_snapshot

    try:
        if not database.is_file():
            raise ValueError("source database absent")
        snapshot = build_review_metrics(create_sqlite_engine(database))
        path, reused = write_snapshot(output_dir, "review-metrics", snapshot)
    except (ValueError, OSError):
        _fail_parse("REVIEW_METRICS_FAILED", "review metrics query or artifact storage failed")
    typer.echo(
        json.dumps(
            {
                "status": "reused" if reused else "stored",
                "artifact_path": str(path),
                "total_candidates": snapshot.total_candidates,
                "pending_candidates": snapshot.pending_candidates,
                "decisions": snapshot.decisions,
                "accuracy_eligible": snapshot.accuracy_eligible,
                "total_score_eligible": snapshot.total_score_eligible,
            },
            ensure_ascii=False,
        )
    )


@score_app.command("readiness")
def score_readiness_command(
    registry: Annotated[Registry, typer.Option("--registry")],
    project_id: Annotated[str, typer.Option("--project-id")],
    database: Annotated[Path, typer.Option("--database")] = Path("data/catchain.sqlite"),
    output_dir: Annotated[Path, typer.Option("--output-dir")] = Path("data/extracted/readiness"),
) -> None:
    from sqlalchemy.exc import SQLAlchemyError

    from catchain.scoring.readiness import project_readiness

    started = datetime.now(UTC)
    try:
        if not database.is_file():
            raise ValueError("source database absent")
        result = project_readiness(
            create_sqlite_engine(database), registry=registry, project_id=project_id
        )
        run = PipelineRun(
            stage=PipelineStage.EVALUATED,
            status=RunStatus.SUCCEEDED,
            input_hash=hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest(),
            config_hash=result["rules_sha256"],
            started_at=started,
            finished_at=datetime.now(UTC),
        )
        result["pipeline_run_id"] = str(run.pipeline_run_id)
        path, stored, reused = store_baseline_artifact(output_dir, result, run)
    except (ValueError, OSError, SQLAlchemyError):
        _fail_parse("READINESS_FAILED", "canonical identity or readiness report storage failed")
    typer.echo(
        json.dumps(
            {
                "status": "reused" if reused else "stored",
                "artifact_path": str(path),
                "pipeline_run_id": stored["run"]["pipeline_run_id"],
                "approved_fact_count": len(result["facts"]),
                "dimension_count": len(result["dimensions"]),
                "methodology_scope": result["methodology_scope"],
                "total_score": None,
                "model_calls": 0,
            }
        )
    )


@score_app.command("checks")
def score_checks_command(
    readiness_artifact: Annotated[Path, typer.Argument()],
    context_file: Annotated[Path | None, typer.Option("--context-file")] = None,
    database: Annotated[Path, typer.Option("--database")] = Path("data/catchain.sqlite"),
    output_dir: Annotated[Path, typer.Option("--output-dir")] = Path(
        "data/extracted/business-checks"
    ),
) -> None:
    from sqlalchemy.exc import SQLAlchemyError

    from catchain.domain.assessment import AssessmentContext
    from catchain.scoring.business_checks import check_business_inputs
    from catchain.scoring.readiness import project_readiness

    started = datetime.now(UTC)
    try:
        if not database.is_file():
            raise ValueError("source database absent")
        bundle = json.loads(readiness_artifact.read_text(encoding="utf-8"))
        prior = PipelineRun.model_validate(bundle["run"])
        readiness = bundle["result"]
        stable = {k: v for k, v in readiness.items() if k != "pipeline_run_id"}
        engine = create_sqlite_engine(database)
        current = project_readiness(
            engine, registry=Registry(readiness["registry"]), project_id=readiness["project_id"]
        )
        if (
            prior.status != RunStatus.SUCCEEDED
            or prior.stage != PipelineStage.EVALUATED
            or readiness["pipeline_run_id"] != str(prior.pipeline_run_id)
            or prior.input_hash
            != hashlib.sha256(json.dumps(stable, sort_keys=True).encode()).hexdigest()
            or prior.config_hash != readiness["rules_sha256"]
            or stable != current
        ):
            raise ValueError("stale or modified readiness snapshot")
        context = (
            AssessmentContext.model_validate_json(context_file.read_text(encoding="utf-8"))
            if context_file
            else None
        )
        result = check_business_inputs(
            readiness, context=context, documents=SqlAlchemyDocumentRepository(engine)
        )
        run = PipelineRun(
            stage=PipelineStage.EVALUATED,
            status=RunStatus.SUCCEEDED,
            input_hash=hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest(),
            config_hash=hashlib.sha256(result["policy_version"].encode()).hexdigest(),
            started_at=started,
            finished_at=datetime.now(UTC),
        )
        result["pipeline_run_id"] = str(run.pipeline_run_id)
        path, stored, reused = store_baseline_artifact(output_dir, result, run)
    except (ValueError, OSError, SQLAlchemyError, KeyError, TypeError):
        _fail_parse(
            "BUSINESS_CHECKS_FAILED",
            "invalid context or stale readiness; regenerate readiness if current facts changed",
        )
    typer.echo(
        json.dumps(
            {
                "status": "reused" if reused else "stored",
                "artifact_path": str(path),
                "pipeline_run_id": stored["run"]["pipeline_run_id"],
                "gate_codes": sorted({g["code"] for g in result["gates"]}),
                "er_diagnostic_status": result["er_diagnostic"]["status"],
                "total_score": None,
                "model_calls": 0,
            }
        )
    )


@score_app.command("judgments")
def save_judgments_command(
    readiness_artifact: Annotated[Path, typer.Argument()],
    request_file: Annotated[Path, typer.Option("--request-file")],
    database: Annotated[Path, typer.Option("--database")] = Path("data/catchain.sqlite"),
    output_dir: Annotated[Path, typer.Option("--output-dir")] = Path("data/extracted/judgments"),
) -> None:
    from sqlalchemy.exc import SQLAlchemyError

    from catchain.domain.judgment import JudgmentRequest
    from catchain.scoring.judgments import grounded_judgments
    from catchain.storage.evaluation_repository import store_evaluation_result

    started = datetime.now(UTC)
    try:
        if not database.is_file():
            raise ValueError("source database absent")
        bundle = json.loads(readiness_artifact.read_text(encoding="utf-8"))
        request = JudgmentRequest.model_validate_json(request_file.read_text(encoding="utf-8"))
        result = grounded_judgments(create_sqlite_engine(database), bundle, request)
        run = PipelineRun(
            stage=PipelineStage.EVALUATED,
            status=RunStatus.SUCCEEDED,
            input_hash=hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest(),
            config_hash=result["rubric_sha256"],
            started_at=started,
            finished_at=datetime.now(UTC),
        )
        result["pipeline_run_id"] = str(run.pipeline_run_id)
        path, stored, reused = store_baseline_artifact(output_dir, result, run)
        evaluation = store_evaluation_result(
            create_sqlite_engine(database),
            stored["result"],
            PipelineRun.model_validate(stored["run"]),
        )
    except (ValueError, OSError, SQLAlchemyError, KeyError, TypeError):
        _fail_parse(
            "JUDGMENTS_FAILED",
            "invalid judgments, stale facts or evidence; request file is preserved",
        )
    typer.echo(
        json.dumps(
            {
                "status": "reused" if reused else "stored",
                "artifact_path": str(path),
                "pipeline_run_id": stored["run"]["pipeline_run_id"],
                "evaluation_result_id": evaluation["evaluation_result_id"],
                "judgment_count": len(request.judgments),
                "unreviewed_count": len(result["unreviewed_criteria"]),
                "total_score": None,
                "model_calls": 0,
            }
        )
    )


@review_app.command("decide")
def review_decide_command(
    request_file: Annotated[Path, typer.Argument()],
    database: Annotated[Path, typer.Option("--database")] = Path("data/catchain.sqlite"),
    draft_dir: Annotated[Path, typer.Option("--draft-dir")] = Path("data/review/drafts"),
) -> None:
    from pydantic import ValidationError
    from sqlalchemy.exc import SQLAlchemyError

    from catchain.domain.review import ReviewRequest
    from catchain.storage.review_repository import ReviewBlocked, decide

    raw = ""
    try:
        raw = request_file.read_text(encoding="utf-8")
        request = ReviewRequest.model_validate_json(raw)
        if not database.is_file():
            raise ReviewBlocked(["source_database_absent"])
        engine = create_sqlite_engine(database)
        create_schema(engine)
        outcome = decide(engine, request)
    except (ValidationError, ReviewBlocked, OSError, SQLAlchemyError) as error:
        if isinstance(error, ValidationError):
            errors = [
                {"loc": list(e["loc"]), "code": e["type"], "message": e["msg"]}
                for e in error.errors(include_input=False, include_context=False)
            ]
        elif isinstance(error, ReviewBlocked):
            errors = [
                {
                    "loc": ["after"]
                    if code.startswith(("evidence_", "date_", "unit_", "field_", "numeric_"))
                    else [],
                    "code": code,
                }
                for code in error.codes
            ]
        else:
            errors = [{"loc": [], "code": "review_storage_failed"}]
        draft_dir.mkdir(parents=True, exist_ok=True)
        path = draft_dir / f"{uuid4()}.json"
        path.write_text(
            json.dumps(
                {"raw_request": raw, "errors": errors, "canonical_writes": 0},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        typer.echo(
            json.dumps(
                {
                    "status": "draft",
                    "draft_path": str(path),
                    "errors": errors,
                    "canonical_writes": 0,
                    "model_calls": 0,
                }
            )
        )
        raise typer.Exit(code=1) from None
    typer.echo(json.dumps({**outcome, "decision_id": str(request.decision_id), "model_calls": 0}))


@review_app.command("candidates")
def review_candidates_command(
    validation_run_id: Annotated[UUID, typer.Argument()],
    database: Annotated[Path, typer.Option("--database")] = Path("data/catchain.sqlite"),
) -> None:
    from sqlalchemy import select

    from catchain.domain.validation import ExtractionValidationReport
    from catchain.storage.database import canonical_heads, fact_candidates, validation_reports

    engine = create_sqlite_engine(database)
    with engine.connect() as connection:
        row = (
            connection.execute(
                select(validation_reports).where(
                    validation_reports.c.pipeline_run_id == str(validation_run_id)
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            _fail_parse("REPORT_ABSENT", "validation report not imported")
        report = ExtractionValidationReport.model_validate_json(row["payload_json"])
        candidates = (
            connection.execute(
                select(fact_candidates)
                .where(fact_candidates.c.validation_run_id == str(validation_run_id))
                .order_by(fact_candidates.c.observation_index)
            )
            .mappings()
            .all()
        )
        result = []
        for candidate in candidates:
            current = connection.execute(
                select(canonical_heads.c.fact_id).where(
                    canonical_heads.c.registry == row["registry"],
                    canonical_heads.c.project_id == row["project_id"],
                    canonical_heads.c.field_name == candidate["field_name"],
                )
            ).scalar_one_or_none()
            result.append(
                {
                    "candidate_id": candidate["candidate_id"],
                    "expected_current_fact_id": current,
                    "check": report.checks[candidate["observation_index"]].model_dump(mode="json"),
                }
            )
    typer.echo(json.dumps({"candidates": result, "model_calls": 0}, ensure_ascii=False))


@store_app.command("validation")
def store_validation_command(
    validation_artifact: Annotated[Path, typer.Argument()],
    extraction_artifact: Annotated[Path, typer.Option("--extraction-artifact")],
    database: Annotated[Path, typer.Option("--database")] = Path("data/catchain.sqlite"),
) -> None:
    from sqlalchemy.exc import SQLAlchemyError

    from catchain.domain.validation import ExtractionValidationReport
    from catchain.storage.fact_repository import SqlAlchemyFactRepository

    try:
        if not database.is_file():
            raise ValueError("source database absent")
        bundle = json.loads(validation_artifact.read_text(encoding="utf-8"))
        report = ExtractionValidationReport.model_validate(bundle["result"])
        run = PipelineRun.model_validate(bundle["run"])
        original = json.loads(extraction_artifact.read_text(encoding="utf-8"))
        extraction = ProjectExtraction.model_validate(original["result"])
        extraction_run = PipelineRun.model_validate(original["run"])
        engine = create_sqlite_engine(database)
        create_schema(engine)
        reused = SqlAlchemyFactRepository(engine).import_validation(
            report, run, extraction, extraction_run
        )
    except (ValueError, OSError, KeyError, TypeError, SQLAlchemyError):
        _fail_parse(
            "STORE_VALIDATION_FAILED", "validation identity, evidence or database import failed"
        )
    typer.echo(
        json.dumps(
            {
                "status": "reused" if reused else "stored",
                "pipeline_run_id": str(run.pipeline_run_id),
                "candidate_count": len(report.checks),
                "evidence_count": sum(len(c.observation.evidence) for c in report.checks),
                "canonical_writes": 0,
                "model_calls": 0,
            }
        )
    )


@schema_app.command("export")
def export_schemas(
    output_dir: Annotated[Path, typer.Option("--output-dir")] = Path("schemas/generated"),
) -> None:
    written = generate_json_schemas(output_dir)
    typer.echo(f"Exported {len(written)} schemas to {output_dir}")


@ingest_app.command("local")
def ingest_local(
    local_file: Annotated[Path, typer.Argument(help="Local source file to import.")],
    registry: Annotated[Registry, typer.Option("--registry")],
    project_id: Annotated[str, typer.Option("--project-id")],
    source_url: Annotated[str, typer.Option("--source-url")],
    document_type: Annotated[DocumentType, typer.Option("--document-type")],
    database: Annotated[Path, typer.Option("--database")] = Path("data/catchain.sqlite"),
    raw_root: Annotated[Path, typer.Option("--raw-root")] = Path("data/raw"),
    content_type: Annotated[str, typer.Option("--content-type")] = "application/pdf",
    declared_version: Annotated[str | None, typer.Option("--declared-version")] = None,
) -> None:
    identity = "|".join((registry.value, project_id, source_url, document_type.value))
    source_document_id = uuid5(NAMESPACE_URL, f"catchain:{identity}")
    engine = create_sqlite_engine(database)
    create_schema(engine)
    repository = SqlAlchemyDocumentRepository(engine)
    source_document = repository.get_source(source_document_id)
    retrieved_at = datetime.now(UTC)
    if source_document is None:
        source_document = SourceDocument(
            source_document_id=source_document_id,
            registry=registry,
            registry_project_id=project_id,
            source_url=source_url,
            document_type=document_type,
            discovered_at=retrieved_at,
        )

    result = ingest_local_document(
        source_document=source_document,
        local_path=local_file,
        content_type=content_type,
        retrieved_at=retrieved_at,
        declared_version=declared_version,
        raw_store=RawBlobStore(raw_root),
        repository=repository,
    )
    action = (
        "Reused existing document version" if result.duplicate else "Stored new document version"
    )
    typer.echo(action)
    typer.echo(f"Document version ID: {result.document_version.document_version_id}")
    typer.echo(f"SHA-256: {result.document_version.sha256}")
    typer.echo(f"Bytes: {result.document_version.byte_size}")
    typer.echo(f"Raw path: {result.raw_path}")


def _configuration_hash(
    parsed: ParsedDocument,
    *,
    quality_policy: TextQualityPolicy,
    page_inspector: RenderedPageInspector,
    ocr_adapter: TesseractOcrAdapter,
) -> str:
    payload = {
        "parser_name": parsed.parser_name,
        "parser_version": parsed.parser_version,
        "min_non_whitespace_count": quality_policy.min_non_whitespace_count,
        "max_replacement_character_ratio": (quality_policy.max_replacement_character_ratio),
        "inspection_dpi": page_inspector.dpi,
        "inspection_white_threshold": page_inspector.white_threshold,
        "inspection_min_ink_ratio": page_inspector.min_ink_ratio,
        "ocr_engine_name": parsed.ocr_engine_name,
        "ocr_engine_version": parsed.ocr_engine_version,
        "ocr_language": ocr_adapter.language,
        "ocr_dpi": ocr_adapter.dpi,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _fail_parse(error_code: str, message: str) -> None:
    typer.echo(json.dumps({"status": "failed", "error_code": error_code, "message": message}))
    raise typer.Exit(code=1)


@parse_app.command("raw")
def parse_raw(
    document_version_id: Annotated[UUID, typer.Argument(help="DocumentVersion UUID to parse.")],
    database: Annotated[Path, typer.Option("--database")] = Path("data/catchain.sqlite"),
    raw_root: Annotated[Path, typer.Option("--raw-root")] = Path("data/raw"),
    min_non_whitespace: Annotated[int, typer.Option("--min-non-whitespace", min=0)] = 80,
    max_replacement_ratio: Annotated[
        float, typer.Option("--max-replacement-ratio", min=0, max=1)
    ] = 0.02,
    tesseract_executable: Annotated[str, typer.Option("--tesseract-executable")] = "tesseract",
    ocr_language: Annotated[str, typer.Option("--ocr-language")] = "eng",
) -> None:
    engine = create_sqlite_engine(database)
    create_schema(engine)
    repository = SqlAlchemyDocumentRepository(engine)
    version = repository.get_version(document_version_id)
    if version is None:
        _fail_parse(
            "DOCUMENT_VERSION_NOT_FOUND",
            f"document version not found: {document_version_id}",
        )

    raw_path = RawBlobStore(raw_root).path_for_hash(version.sha256)
    if not raw_path.is_file():
        _fail_parse("RAW_FILE_NOT_FOUND", f"raw file not found: {raw_path}")

    quality_policy = TextQualityPolicy(
        min_non_whitespace_count=min_non_whitespace,
        max_replacement_character_ratio=max_replacement_ratio,
    )
    page_inspector = RenderedPageInspector()
    ocr_adapter = TesseractOcrAdapter(
        executable=tesseract_executable,
        language=ocr_language,
    )
    try:
        parsed = parse_with_ocr_fallback(
            raw_path,
            document_version_id,
            ocr_adapter=ocr_adapter,
            quality_policy=quality_policy,
            page_inspector=page_inspector,
        )
    except OcrError as error:
        _fail_parse(type(error).__name__, str(error))
    except PdfParseError as error:
        _fail_parse(type(error).__name__, str(error))

    configuration_hash = _configuration_hash(
        parsed,
        quality_policy=quality_policy,
        page_inspector=page_inspector,
        ocr_adapter=ocr_adapter,
    )
    existing = repository.find_parsed(document_version_id, configuration_hash)
    if existing is None:
        repository.add_parsed(parsed, configuration_hash=configuration_hash)
        stored = parsed
        status = "stored"
    else:
        stored = existing
        status = "reused"

    typer.echo(
        json.dumps(
            {
                "status": status,
                "parsed_document_id": str(stored.parsed_document_id),
                "document_version_id": str(stored.document_version_id),
                "configuration_hash": configuration_hash,
                "page_count": len(stored.pages),
                "ocr_page_count": sum(page.used_ocr for page in stored.pages),
                "warnings": list(stored.warnings),
            }
        )
    )


def _run_baseline(
    parsed_document_id: UUID,
    database: Path,
    output_dir: Path,
    *,
    project_id: str | None = None,
    registry: Registry | None = None,
) -> None:
    engine = create_sqlite_engine(database)
    create_schema(engine)
    repository = SqlAlchemyDocumentRepository(engine)
    parsed = repository.get_parsed(parsed_document_id)
    if parsed is None:
        _fail_parse("PARSED_DOCUMENT_NOT_FOUND", f"parsed document not found: {parsed_document_id}")
    version = repository.get_version(parsed.document_version_id)
    source = repository.get_source(version.source_document_id) if version else None
    if source is None:
        _fail_parse("SOURCE_NOT_FOUND", "Parsed document has no source identity")
    started = datetime.now(UTC)
    run_id = uuid4()
    if project_id is not None:
        if project_id != source.registry_project_id or registry != source.registry:
            _fail_parse("SOURCE_IDENTITY_MISMATCH", "project/registry differ from imported source")
        result = extract_regex(parsed, project_id, registry, pipeline_run_id=run_id)
        payload = result.model_dump(mode="json")
        config = {
            "rules": RULES,
            "extractor_version": result.extractor_version,
            "schema_version": result.schema_version,
        }
        stage = PipelineStage.BASELINE_EXTRACTED
    else:
        payload = score_keywords((parsed,))
        payload["pipeline_run_id"] = str(run_id)
        config = {
            "baseline_version": payload["baseline_version"],
            "rules_sha256": payload["rules_sha256"],
        }
        stage = PipelineStage.SCORED
    run = PipelineRun(
        pipeline_run_id=run_id,
        stage=stage,
        status=RunStatus.SUCCEEDED,
        input_hash=hashlib.sha256(parsed.model_dump_json().encode()).hexdigest(),
        config_hash=hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest(),
        started_at=started,
        finished_at=datetime.now(UTC),
    )
    try:
        path, bundle, reused = store_baseline_artifact(output_dir, payload, run)
    except ArtifactConflictError as error:
        _fail_parse("ARTIFACT_CONFLICT", str(error))
    except OSError as error:
        _fail_parse("ARTIFACT_WRITE_FAILED", str(error))
    stored = bundle["result"]
    summary = {
        "status": "reused" if reused else "stored",
        "artifact_path": str(path),
        "artifact_name": path.name,
        "parsed_document_id": str(parsed_document_id),
        "document_version_id": str(parsed.document_version_id),
        "pipeline_run_id": stored["pipeline_run_id"],
        "project_id": source.registry_project_id,
        "registry": source.registry.value,
        "source_url": str(source.source_url),
        "source_sha256": version.sha256,
    }
    if project_id is not None:
        observations = stored["observations"]
        matched = {o["field_name"] for o in observations if o["missing_reason"] is None}
        missing = {o["field_name"] for o in observations if o["missing_reason"] is not None}
        candidate_values = {
            field: {
                json.dumps(o["normalized_value"])
                for o in observations
                if o["field_name"] == field and o["missing_reason"] is None
            }
            for field in matched
        }
        summary.update(
            extractor_version=stored["extractor_version"],
            schema_version=stored["schema_version"],
            matched_fields=len(matched),
            missing_fields=len(missing),
            matched_field_coverage=len(matched) / (len(matched) + len(missing)),
            candidate_conflict_fields=sum(len(values) > 1 for values in candidate_values.values()),
        )
    else:
        summary.update(
            baseline_version=stored["baseline_version"],
            total_score=stored["total_score"],
            max_score=stored["max_score"],
            keyword_score_ratio=stored["keyword_score_ratio"],
        )
    typer.echo(json.dumps(summary))


@extract_app.command("baseline")
def extract_baseline(
    parsed_document_id: Annotated[UUID, typer.Argument()],
    project_id: Annotated[str, typer.Option("--project-id")],
    registry: Annotated[Registry, typer.Option("--registry")],
    database: Annotated[Path, typer.Option("--database")] = Path("data/catchain.sqlite"),
    output_dir: Annotated[Path, typer.Option("--output-dir")] = Path("data/extracted"),
) -> None:
    _run_baseline(
        parsed_document_id, database, output_dir, project_id=project_id, registry=registry
    )


@score_app.command("keywords")
def score_keyword_baseline(
    parsed_document_id: Annotated[UUID, typer.Argument()],
    database: Annotated[Path, typer.Option("--database")] = Path("data/catchain.sqlite"),
    output_dir: Annotated[Path, typer.Option("--output-dir")] = Path("data/extracted"),
) -> None:
    _run_baseline(parsed_document_id, database, output_dir)


@extract_app.command("llm-once")
def extract_llm_once(
    parsed_document_id: Annotated[UUID, typer.Argument()],
    pages: Annotated[list[int], typer.Option("--page", min=1)],
    fields: Annotated[list[str], typer.Option("--field")],
    database: Annotated[Path, typer.Option("--database")] = Path("data/catchain.sqlite"),
    output_dir: Annotated[Path, typer.Option("--output-dir")] = Path("data/extracted/llm"),
    config_file: Annotated[Path, typer.Option("--config-file")] = Path(".env"),
    model: Annotated[str, typer.Option("--model")] = "deepseek-flash",
    max_output_tokens: Annotated[int, typer.Option("--max-output-tokens", min=1, max=4096)] = 1024,
    input_cost_per_million_usd: Annotated[
        str | None, typer.Option("--input-cost-per-million-usd")
    ] = None,
    output_cost_per_million_usd: Annotated[
        str | None, typer.Option("--output-cost-per-million-usd")
    ] = None,
    max_estimated_cost_usd: Annotated[str | None, typer.Option("--max-estimated-cost-usd")] = None,
) -> None:
    """One bounded development call; matching completed inputs reuse an existing result."""
    from catchain.extraction.llm.providers import (
        DeepSeekProvider,
        ProviderError,
        read_deepseek_key,
    )
    from catchain.extraction.llm.workflow import CostRates, extract_one_call

    repository = SqlAlchemyDocumentRepository(create_sqlite_engine(database))
    parsed = repository.get_parsed(parsed_document_id)
    if parsed is None:
        _fail_parse("PARSED_DOCUMENT_NOT_FOUND", "Parsed document not found")
    version = repository.get_version(parsed.document_version_id)
    source = repository.get_source(version.source_document_id) if version else None
    if source is None:
        _fail_parse("SOURCE_NOT_FOUND", "Parsed document has no source identity")
    try:
        prices = (input_cost_per_million_usd, output_cost_per_million_usd)
        if any(prices) and not all(prices):
            raise ValueError("provide both input and output token prices")
        cost_rates = CostRates(Decimal(prices[0]), Decimal(prices[1])) if all(prices) else None
        maximum_cost = Decimal(max_estimated_cost_usd) if max_estimated_cost_usd else None
        provider = DeepSeekProvider(api_key=read_deepseek_key(config_file), model=model)
        artifact = extract_one_call(
            parsed,
            provider=provider,
            page_numbers=tuple(pages),
            requested_fields=tuple(fields),
            project_id=source.registry_project_id,
            registry=source.registry,
            output_dir=output_dir,
            max_output_tokens=max_output_tokens,
            cost_rates=cost_rates,
            max_estimated_cost_usd=maximum_cost,
        )
    except (InvalidOperation, ProviderError, ValueError, OSError) as error:
        message = (
            str(error) if isinstance(error, ProviderError) else "invalid input or storage failed"
        )
        _fail_parse("LLM_EXTRACTION_FAILED", message)
    result = json.loads(artifact.path.read_text())
    configuration = result["configuration"]
    response_path = output_dir / "runs" / result["run"]["pipeline_run_id"] / "response.json"
    response = json.loads(response_path.read_text())
    typer.echo(
        json.dumps(
            {
                "status": "reused" if artifact.reused else "stored",
                "artifact_path": str(artifact.path),
                "project_id": source.registry_project_id,
                "registry": source.registry.value,
                "pipeline_run_id": result["run"]["pipeline_run_id"],
                "input_tokens": response["input_tokens"],
                "output_tokens": response["output_tokens"],
                "latency_seconds": response["latency_seconds"],
                "estimated_cost_usd": result["call_metrics"]["actual_estimated_cost_usd"],
                "worst_case_estimated_cost_usd": configuration["worst_case_estimated_cost_usd"],
                "validation_status": "unvalidated",
                "cache_enabled": True,
            }
        )
    )


@compare_app.command("extraction")
def compare_extraction_command(
    llm_artifact: Annotated[Path, typer.Argument()],
    database: Annotated[Path, typer.Option("--database")] = Path("data/catchain.sqlite"),
    output_dir: Annotated[Path, typer.Option("--output-dir")] = Path("data/extracted/comparison"),
) -> None:
    """Offline Regex/LLM candidate differences; does not call a model."""
    from catchain.extraction.comparison import compare_extraction

    started_at = datetime.now(UTC)
    try:
        bundle = json.loads(llm_artifact.read_text(encoding="utf-8"))
        llm = ProjectExtraction.model_validate(bundle["result"])
        start_path = llm_artifact.parent / "started.json"
        if not start_path.is_file():
            start_path = (
                llm_artifact.parent.parent / "runs" / str(llm.pipeline_run_id) / "started.json"
            )
        started = json.loads(start_path.read_text(encoding="utf-8"))
        repository = SqlAlchemyDocumentRepository(create_sqlite_engine(database))
        parsed = repository.get_parsed(llm.parsed_document_id)
        if parsed is None:
            raise ValueError("Parsed document absent")
        version = repository.get_version(parsed.document_version_id)
        source = repository.get_source(version.source_document_id) if version else None
        if source is None or (source.registry_project_id, source.registry) != (
            llm.project_id,
            llm.registry,
        ):
            raise ValueError("source identity mismatch")
        report = compare_extraction(parsed, bundle, started)
        report["source_sha256"] = version.sha256
        run_id = uuid4()
        report["pipeline_run_id"] = str(run_id)
        run = PipelineRun(
            pipeline_run_id=run_id,
            stage=PipelineStage.EVALUATED,
            status=RunStatus.SUCCEEDED,
            input_hash=hashlib.sha256(parsed.model_dump_json().encode()).hexdigest(),
            config_hash=hashlib.sha256(
                json.dumps(
                    {
                        "comparison_version": "fixed-pages-v1",
                        "comparison_id": report["comparison_id"],
                    },
                    sort_keys=True,
                ).encode()
            ).hexdigest(),
            started_at=started_at,
            finished_at=datetime.now(UTC),
        )
        path, stored, reused = store_baseline_artifact(output_dir, report, run)
    except (ValueError, OSError, KeyError, TypeError):
        _fail_parse("COMPARISON_FAILED", "artifact/source/evidence validation or storage failed")
    typer.echo(
        json.dumps(
            {
                "status": "reused" if reused else "stored",
                "artifact_path": str(path),
                "pipeline_run_id": stored["run"]["pipeline_run_id"],
                "counts": stored["result"]["counts"],
                "accuracy": None,
                "gold_status": "not_available",
                "model_calls": 0,
            }
        )
    )


@evaluate_app.command("gold")
def evaluate_gold_command(
    gold_file: Annotated[Path, typer.Argument()],
    extraction_artifact: Annotated[Path, typer.Argument()],
    output_dir: Annotated[Path, typer.Option("--output-dir")] = Path(
        "data/extracted/gold-evaluation"
    ),
) -> None:
    """Evaluate one extraction against a frozen GoldSample without model calls."""
    from catchain.domain.gold import GoldSample
    from catchain.extraction.gold_evaluation import evaluate_against_gold

    started_at = datetime.now(UTC)
    try:
        gold = GoldSample.model_validate_json(gold_file.read_text(encoding="utf-8"))
        bundle = json.loads(extraction_artifact.read_text(encoding="utf-8"))
        extraction = ProjectExtraction.model_validate(bundle["result"])
        prior_run = PipelineRun.model_validate(bundle["run"])
        if (
            prior_run.status != RunStatus.SUCCEEDED
            or prior_run.stage
            not in {PipelineStage.BASELINE_EXTRACTED, PipelineStage.LLM_EXTRACTED}
            or extraction.pipeline_run_id != prior_run.pipeline_run_id
        ):
            raise ValueError("extraction artifact/run identity is not evaluable")
        report = evaluate_against_gold(gold, extraction)
        report["pipeline_run_id"] = str(uuid4())
        identity = {
            "extraction_pipeline_run_id": str(prior_run.pipeline_run_id),
            "gold_dataset_version": gold.dataset_version,
            "gold_sample_id": gold.sample_id,
            "metric_version": "gold-evaluation-v1",
        }
        run = PipelineRun(
            pipeline_run_id=UUID(report["pipeline_run_id"]),
            stage=PipelineStage.EVALUATED,
            status=RunStatus.SUCCEEDED,
            input_hash=hashlib.sha256(
                json.dumps(
                    {
                        "extraction": extraction.model_dump(mode="json"),
                        "gold": gold.model_dump(mode="json"),
                    },
                    sort_keys=True,
                ).encode()
            ).hexdigest(),
            config_hash=hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest(),
            started_at=started_at,
            finished_at=datetime.now(UTC),
        )
        path, stored, reused = store_baseline_artifact(output_dir, report, run)
    except (ValueError, OSError, KeyError, TypeError):
        _fail_parse("GOLD_EVALUATION_FAILED", "frozen Gold and extraction artifact are required")
    typer.echo(
        json.dumps(
            {
                "status": "reused" if reused else "stored",
                "artifact_path": str(path),
                "pipeline_run_id": stored["run"]["pipeline_run_id"],
                "gold_status": stored["result"]["gold_status"],
                "sample_id": stored["result"]["sample_id"],
                "metrics": stored["result"]["metrics"],
                "model_calls": 0,
            }
        )
    )


@evaluate_app.command("dataset")
def evaluate_dataset_command(
    dataset_file: Annotated[Path, typer.Argument()],
    report_dir: Annotated[Path, typer.Argument()],
    split: Annotated[str | None, typer.Option("--split")] = None,
    output_dir: Annotated[Path, typer.Option("--output-dir")] = Path(
        "data/extracted/gold-evaluation"
    ),
) -> None:
    """Aggregate complete frozen-Gold reports without model calls."""
    from catchain.domain.gold import GoldDataset
    from catchain.extraction.gold_evaluation import aggregate_gold_evaluations

    started_at = datetime.now(UTC)
    try:
        if split is not None and split not in {"development", "validation", "test"}:
            raise ValueError("split must be development, validation or test")
        dataset = GoldDataset.model_validate_json(dataset_file.read_text(encoding="utf-8"))
        if not report_dir.is_dir():
            raise ValueError("evaluation report directory absent")
        reports = []
        for report_path in sorted(report_dir.glob("*.json")):
            bundle = json.loads(report_path.read_text(encoding="utf-8"))
            reports.append(bundle["result"])
        report = aggregate_gold_evaluations(dataset, tuple(reports), split=split)
        report["pipeline_run_id"] = str(uuid4())
        identity = {
            "dataset_version": dataset.dataset_version,
            "split": split or "all",
            "metric_version": "gold-evaluation-v1",
        }
        run = PipelineRun(
            pipeline_run_id=UUID(report["pipeline_run_id"]),
            stage=PipelineStage.EVALUATED,
            status=RunStatus.SUCCEEDED,
            input_hash=hashlib.sha256(
                json.dumps(
                    {"dataset": dataset.model_dump(mode="json"), "reports": reports},
                    sort_keys=True,
                ).encode()
            ).hexdigest(),
            config_hash=hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest(),
            started_at=started_at,
            finished_at=datetime.now(UTC),
        )
        path, stored, reused = store_baseline_artifact(output_dir, report, run)
    except (ValueError, OSError, KeyError, TypeError):
        _fail_parse(
            "GOLD_DATASET_EVALUATION_FAILED",
            "frozen dataset and complete reports are required",
        )
    typer.echo(
        json.dumps(
            {
                "status": "reused" if reused else "stored",
                "artifact_path": str(path),
                "pipeline_run_id": stored["run"]["pipeline_run_id"],
                "dataset_version": stored["result"]["dataset_version"],
                "split": stored["result"]["split"],
                "metrics": stored["result"]["metrics"],
                "model_calls": 0,
            }
        )
    )


@validate_app.command("extraction")
def validate_extraction_command(
    extraction_artifact: Annotated[Path, typer.Argument()],
    database: Annotated[Path, typer.Option("--database")] = Path("data/catchain.sqlite"),
    output_dir: Annotated[Path, typer.Option("--output-dir")] = Path("data/extracted/validation"),
    confidence_threshold: Annotated[
        float, typer.Option("--confidence-threshold", min=0, max=1)
    ] = 0.8,
) -> None:
    """Mechanical candidate checks; no model calls and no canonical writes."""
    from catchain.validation.extraction import validate_extraction

    started_at = datetime.now(UTC)
    try:
        bundle = json.loads(extraction_artifact.read_text(encoding="utf-8"))
        extraction = ProjectExtraction.model_validate(bundle["result"])
        prior_run = PipelineRun.model_validate(bundle["run"])
        repository = SqlAlchemyDocumentRepository(create_sqlite_engine(database))
        parsed = repository.get_parsed(extraction.parsed_document_id)
        if parsed is None:
            raise ValueError("Parsed document absent")
        version = repository.get_version(parsed.document_version_id)
        source = repository.get_source(version.source_document_id) if version else None
        input_hash = hashlib.sha256(parsed.model_dump_json().encode()).hexdigest()
        if (
            source is None
            or source.registry_project_id != extraction.project_id
            or source.registry != extraction.registry
            or prior_run.pipeline_run_id != extraction.pipeline_run_id
            or prior_run.status is not RunStatus.SUCCEEDED
            or prior_run.stage
            not in {PipelineStage.BASELINE_EXTRACTED, PipelineStage.LLM_EXTRACTED}
            or prior_run.input_hash != input_hash
        ):
            raise ValueError("extraction/source/run identity mismatch")
        run_id = uuid4()
        report = validate_extraction(
            parsed,
            extraction,
            pipeline_run_id=run_id,
            confidence_threshold=confidence_threshold,
        )
        configuration = {
            "validator_version": report.validator_version,
            "confidence_threshold": confidence_threshold,
            "extraction_sha256": hashlib.sha256(extraction.model_dump_json().encode()).hexdigest(),
        }
        run = PipelineRun(
            pipeline_run_id=run_id,
            stage=PipelineStage.QUALITY_VALIDATED,
            status=RunStatus.SUCCEEDED,
            input_hash=input_hash,
            config_hash=hashlib.sha256(
                json.dumps(configuration, sort_keys=True).encode()
            ).hexdigest(),
            started_at=started_at,
            finished_at=datetime.now(UTC),
        )
        path, stored, reused = store_baseline_artifact(
            output_dir, report.model_dump(mode="json"), run
        )
    except (ValueError, OSError, KeyError, TypeError):
        _fail_parse("VALIDATION_FAILED", "artifact/source/run validation or report storage failed")
    checks = stored["result"]["checks"]
    typer.echo(
        json.dumps(
            {
                "status": "reused" if reused else "stored",
                "artifact_path": str(path),
                "pipeline_run_id": stored["run"]["pipeline_run_id"],
                "counts": {
                    name: sum(item["status"] == name for item in checks)
                    for name in ("missing", "rejected", "needs_review")
                },
                "canonical_writes": 0,
                "model_calls": 0,
            }
        )
    )


@validate_app.command("project")
def validate_project_command(
    validation_artifacts: Annotated[list[Path], typer.Argument()],
    database: Annotated[Path, typer.Option("--database")] = Path("data/catchain.sqlite"),
    output_dir: Annotated[Path, typer.Option("--output-dir")] = Path("data/extracted/consistency"),
) -> None:
    """Offline consistency checks on one project's validated candidate reports."""
    from catchain.domain.consistency import ValidationInput
    from catchain.domain.validation import ExtractionValidationReport
    from catchain.validation.consistency import validate_project

    started_at = datetime.now(UTC)
    try:
        if not 1 <= len(validation_artifacts) <= 20:
            raise ValueError("select between one and twenty reports")
        repository = SqlAlchemyDocumentRepository(create_sqlite_engine(database))
        inputs = []
        for artifact in validation_artifacts:
            bundle = json.loads(artifact.read_text(encoding="utf-8"))
            report = ExtractionValidationReport.model_validate(bundle["result"])
            prior_run = PipelineRun.model_validate(bundle["run"])
            parsed = repository.get_parsed(report.parsed_document_id)
            version = repository.get_version(report.document_version_id)
            source = repository.get_source(version.source_document_id) if version else None
            if (
                parsed is None
                or version is None
                or source is None
                or parsed.document_version_id != report.document_version_id
                or (source.registry_project_id, source.registry)
                != (report.project_id, report.registry)
                or prior_run.pipeline_run_id != report.pipeline_run_id
                or prior_run.status is not RunStatus.SUCCEEDED
                or prior_run.stage is not PipelineStage.QUALITY_VALIDATED
                or prior_run.input_hash
                != hashlib.sha256(parsed.model_dump_json().encode()).hexdigest()
            ):
                raise ValueError("validation/source/run identity mismatch")
            # Input reports remain untrusted files: check linked source quotes again.
            for check in report.checks:
                for evidence in check.observation.evidence:
                    if (
                        evidence.document_version_id != version.document_version_id
                        or not 1 <= evidence.page_number <= len(parsed.pages)
                    ):
                        if check.status != "rejected":
                            raise ValueError("nonrejected evidence has invalid source identity")
                        continue
                    text = parsed.pages[evidence.page_number - 1].text
                    if check.status != "rejected" and (
                        not evidence.quote.strip()
                        or evidence.quote not in text
                        or (
                            evidence.char_start is not None
                            and (
                                evidence.char_end > len(text)
                                or text[evidence.char_start : evidence.char_end] != evidence.quote
                            )
                        )
                    ):
                        raise ValueError("nonrejected evidence differs from source")
            inputs.append(
                ValidationInput(
                    report=report,
                    source_document_id=source.source_document_id,
                    document_type=source.document_type,
                    sha256=version.sha256,
                    declared_version=version.declared_version,
                    retrieved_at=version.retrieved_at,
                )
            )
        run_id = uuid4()
        report = validate_project(tuple(inputs), pipeline_run_id=run_id)
        payload = report.model_dump(mode="json")
        identity = {key: value for key, value in payload.items() if key != "pipeline_run_id"}
        identity_hash = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        run = PipelineRun(
            pipeline_run_id=run_id,
            stage=PipelineStage.QUALITY_VALIDATED,
            status=RunStatus.SUCCEEDED,
            input_hash=identity_hash,
            config_hash=hashlib.sha256(
                json.dumps(
                    {
                        "rule_version": report.rule_version,
                        "authority_policy": report.authority_policy,
                    },
                    sort_keys=True,
                ).encode()
            ).hexdigest(),
            started_at=started_at,
            finished_at=datetime.now(UTC),
        )
        path, stored, reused = store_baseline_artifact(output_dir, payload, run)
    except (ValueError, OSError, KeyError, TypeError):
        _fail_parse(
            "CONSISTENCY_FAILED", "input/source/evidence validation or report storage failed"
        )
    result = stored["result"]
    typer.echo(
        json.dumps(
            {
                "status": "reused" if reused else "stored",
                "artifact_path": str(path),
                "pipeline_run_id": stored["run"]["pipeline_run_id"],
                "issue_count": len(result["issues"]),
                "issue_codes": sorted({issue["code"] for issue in result["issues"]}),
                "cross_document_comparison": result["cross_document_comparison"],
                "authority_policy": result["authority_policy"],
                "canonical_writes": 0,
                "model_calls": 0,
            }
        )
    )
