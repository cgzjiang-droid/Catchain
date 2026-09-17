"""One bounded call with durable start/response/failure records; no canonical writes."""

import hashlib
import json
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from importlib.resources import files
from pathlib import Path
from typing import get_args

from catchain.domain import ParsedDocument, PipelineRun, PipelineStage, Registry, RunStatus
from catchain.domain.extraction import FieldName
from catchain.extraction.llm.contract import (
    ModelResponse,
    StructuredProvider,
    ground_response,
    select_pages,
)
from catchain.extraction.llm.providers import ProviderError


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


@dataclass(frozen=True)
class CostRates:
    """Explicit USD prices per million tokens; never silently assume a price."""

    input_per_million_usd: Decimal
    output_per_million_usd: Decimal

    def __post_init__(self) -> None:
        if self.input_per_million_usd < 0 or self.output_per_million_usd < 0:
            raise ValueError("token prices must be non-negative")


@dataclass(frozen=True)
class ExtractionArtifact:
    path: Path
    reused: bool


def _money(value: Decimal) -> str:
    return format(value, "f")


def _estimated_cost(input_tokens: int, output_tokens: int, rates: CostRates | None) -> str | None:
    if rates is None:
        return None
    return _money(
        (
            Decimal(input_tokens) * rates.input_per_million_usd
            + Decimal(output_tokens) * rates.output_per_million_usd
        )
        / Decimal(1_000_000)
    )


def _read_cached(path: Path, configuration: dict) -> bool:
    try:
        cached = json.loads(path.read_text(encoding="utf-8"))
        run = PipelineRun.model_validate(cached["run"])
        return (
            run.status is RunStatus.SUCCEEDED
            and cached["configuration"] == configuration
            and cached["result"]["pipeline_run_id"] == str(run.pipeline_run_id)
        )
    except (OSError, ValueError, KeyError, TypeError):
        return False


def _write_once(path: Path, payload: dict) -> None:
    """Publish a completed cache entry atomically without replacing prior evidence."""
    temporary = path.with_name(path.name + ".tmp-" + str(os.getpid()))
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def extract_one_call(
    parsed: ParsedDocument,
    *,
    provider: StructuredProvider,
    page_numbers: tuple[int, ...],
    requested_fields: tuple[FieldName, ...],
    project_id: str,
    registry: Registry,
    output_dir: Path,
    max_output_tokens: int = 1024,
    cost_rates: CostRates | None = None,
    max_estimated_cost_usd: Decimal | None = None,
) -> ExtractionArtifact:
    """At most one paid call, with a completed-input cache and an optional cost ceiling."""
    pages = select_pages(parsed, page_numbers)
    if (
        not requested_fields
        or len(set(requested_fields)) != len(requested_fields)
        or any(field not in get_args(FieldName) for field in requested_fields)
    ):
        raise ValueError("request nonempty unique known fields")
    if not 1 <= max_output_tokens <= 4096 or not project_id.strip():
        raise ValueError("invalid output budget or project identity")
    prompt = files("catchain.extraction.llm").joinpath("prompt-v1.txt").read_text()
    schema = ModelResponse.model_json_schema()
    input_json = json.dumps(
        {
            "requested_fields": requested_fields,
            "schema": schema,
            "pages": [{"page_number": page.page_number, "text": page.text} for page in pages],
        },
        ensure_ascii=False,
    )
    if len(input_json.encode()) + len(prompt.encode()) > 60000:
        raise ValueError("prompt/input byte budget exceeded")
    if max_estimated_cost_usd is not None and max_estimated_cost_usd < 0:
        raise ValueError("maximum estimated cost must be non-negative")
    input_token_upper_bound = len((prompt + input_json).encode())
    worst_case_cost = _estimated_cost(input_token_upper_bound, max_output_tokens, cost_rates)
    if max_estimated_cost_usd is not None:
        if cost_rates is None:
            raise ValueError("cost ceiling requires explicit input and output token prices")
        if Decimal(worst_case_cost) > max_estimated_cost_usd:
            raise ValueError("worst-case estimated cost exceeds configured ceiling")
    configuration = {
        "provider": provider.name,
        "model": provider.model,
        "prompt_version": "carbon-extraction-v1",
        "prompt_hash": digest(prompt),
        "schema_version": "model-response-v1/project-extraction-1.1.0",
        "schema_hash": digest(json.dumps(schema, sort_keys=True)),
        "selected_pages_hash": digest(
            json.dumps(
                [{"number": page.page_number, "text": page.text} for page in pages], sort_keys=True
            )
        ),
        "requested_fields": list(requested_fields),
        "max_output_tokens": max_output_tokens,
        "input_token_upper_bound": input_token_upper_bound,
        "max_calls": 1,
        "retry_count": 0,
        "input_cost_per_million_usd": (
            _money(cost_rates.input_per_million_usd) if cost_rates else None
        ),
        "output_cost_per_million_usd": (
            _money(cost_rates.output_per_million_usd) if cost_rates else None
        ),
        "worst_case_estimated_cost_usd": worst_case_cost,
        "cost_status": "configured" if cost_rates else "pricing_not_configured",
    }
    cache_key = digest(
        json.dumps(
            {
                "document_version_id": str(parsed.document_version_id),
                "parsed_document_hash": digest(parsed.model_dump_json()),
                "configuration": configuration,
            },
            sort_keys=True,
        )
    )
    run = PipelineRun(
        stage=PipelineStage.LLM_EXTRACTED,
        status=RunStatus.RUNNING,
        input_hash=digest(parsed.model_dump_json()),
        config_hash=digest(json.dumps(configuration, sort_keys=True)),
        started_at=datetime.now(UTC),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = output_dir / "cache"
    cache_dir.mkdir(exist_ok=True)
    cache_path = cache_dir / f"{cache_key}.json"
    if cache_path.exists():
        if _read_cached(cache_path, configuration):
            return ExtractionArtifact(path=cache_path, reused=True)
        raise ProviderError(f"cached artifact conflict: {cache_path}")
    lock_dir = output_dir / ".locks"
    lock_dir.mkdir(exist_ok=True)
    lock_path = lock_dir / cache_key
    try:
        lock_path.mkdir()
    except FileExistsError:
        raise ProviderError(f"matching extraction is already in progress: {lock_path}") from None
    directory = output_dir / "runs" / str(run.pipeline_run_id)
    directory.mkdir(parents=True)

    def write(name, payload):
        with (directory / name).open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())

    write(
        "started.json",
        {
            "run": run.model_dump(mode="json"),
            "configuration": configuration,
            "parsed_document_id": str(parsed.parsed_document_id),
            "document_version_id": str(parsed.document_version_id),
            "project_id": project_id,
            "registry": registry.value,
            "selected_page_numbers": [page.page_number for page in pages],
        },
    )
    started = time.monotonic()
    try:
        if cache_path.exists():
            if _read_cached(cache_path, configuration):
                return ExtractionArtifact(path=cache_path, reused=True)
            raise ProviderError(f"cached artifact conflict: {cache_path}")
        reply = provider.extract(
            system_prompt=prompt, input_json=input_json, max_output_tokens=max_output_tokens
        )
        write("response.json", reply.model_dump(mode="json"))
        if reply.finish_reason != "stop":
            raise ProviderError("LLM output unfinished/refused: " + reply.finish_reason)
        if not reply.content.strip():
            raise ProviderError("LLM returned empty content")
        result = ground_response(
            reply.content,
            parsed,
            selected_page_numbers=tuple(page.page_number for page in pages),
            requested_fields=requested_fields,
            project_id=project_id,
            registry=registry,
            pipeline_run_id=run.pipeline_run_id,
            extractor_name=provider.name,
            extractor_version="carbon-extraction-v1:" + reply.model,
        )
        finished = PipelineRun(
            **{
                **run.model_dump(),
                "status": RunStatus.SUCCEEDED,
                "finished_at": datetime.now(UTC),
            }
        )
        write(
            "result.json",
            {
                "result": result.model_dump(mode="json"),
                "run": finished.model_dump(mode="json"),
                "configuration": configuration,
                "call_metrics": {
                    "actual_estimated_cost_usd": _estimated_cost(
                        reply.input_tokens, reply.output_tokens, cost_rates
                    )
                },
            },
        )
        payload = json.loads((directory / "result.json").read_text(encoding="utf-8"))
        _write_once(cache_path, payload)
    except (ProviderError, ValueError, OSError) as error:
        # Do not leak Pydantic input_value, raw quotes, keys or provider error bodies in logs.
        code = type(error).__name__
        message = str(error) if isinstance(error, ProviderError) else "validation or storage failed"
        failed = PipelineRun(
            **{
                **run.model_dump(),
                "status": RunStatus.FAILED,
                "finished_at": datetime.now(UTC),
                "error_code": code,
                "error_message": message,
            }
        )
        write(
            "failed.json",
            {"run": failed.model_dump(mode="json"), "elapsed_seconds": time.monotonic() - started},
        )
        raise ProviderError(f"{message}; failure record: {directory}") from None
    finally:
        lock_path.rmdir()
    return ExtractionArtifact(path=cache_path, reused=False)
