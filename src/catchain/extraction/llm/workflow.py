"""One bounded call with durable start/response/failure records; no canonical writes."""

import hashlib
import json
import os
import time
from datetime import UTC, datetime
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
) -> Path:
    """Explicit development call. No cache yet: every invocation may incur cost."""
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
        "requested_fields": requested_fields,
        "max_output_tokens": max_output_tokens,
        "max_calls": 1,
        "retry_count": 0,
        "estimated_cost": None,
        "cost_status": "pricing_not_configured",
    }
    run = PipelineRun(
        stage=PipelineStage.LLM_EXTRACTED,
        status=RunStatus.RUNNING,
        input_hash=digest(parsed.model_dump_json()),
        config_hash=digest(json.dumps(configuration, sort_keys=True)),
        started_at=datetime.now(UTC),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    directory = output_dir / str(run.pipeline_run_id)
    directory.mkdir()  # Unique run; never replace earlier response or failure evidence.

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
            },
        )
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
    return directory / "result.json"
