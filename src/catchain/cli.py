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
compare_app = typer.Typer(help="Compare candidates on identical selected pages.")
validate_app = typer.Typer(help="Check candidate types, evidence and review requirements.")
app.add_typer(schema_app, name="schema")
app.add_typer(ingest_app, name="ingest")
app.add_typer(parse_app, name="parse")
app.add_typer(extract_app, name="extract")
app.add_typer(score_app, name="score")
app.add_typer(compare_app, name="compare")
app.add_typer(validate_app, name="validate")
store_app = typer.Typer(help="Persist validated candidates without canonical promotion.")
app.add_typer(store_app, name="store")


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
