"""Immutable derived JSON bundles; candidate facts are not canonical database rows."""

import hashlib
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from catchain.domain import PipelineRun, RunStatus


class ArtifactConflictError(ValueError):
    """An existing artifact cannot be safely reused."""


def _stable_result(result: dict) -> dict:
    return {
        key: value for key, value in result.items() if key not in {"created_at", "pipeline_run_id"}
    }


def store_baseline_artifact(
    output_dir: Path, result: dict, run: PipelineRun
) -> tuple[Path, dict, bool]:
    identity = {
        "result": _stable_result(result),
        "input_hash": run.input_hash,
        "config_hash": run.config_hash,
        "stage": run.stage.value,
    }
    key = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode())
    path = output_dir / f"{run.stage.value}-{key.hexdigest()}.json"

    def reuse() -> tuple[Path, dict, bool]:
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
            cached_run = PipelineRun.model_validate(cached["run"])
            if (
                _stable_result(cached["result"]) != identity["result"]
                or cached_run.input_hash != run.input_hash
                or cached_run.config_hash != run.config_hash
                or cached_run.stage != run.stage
                or cached_run.status != RunStatus.SUCCEEDED
                or cached["result"]["pipeline_run_id"] != str(cached_run.pipeline_run_id)
            ):
                raise ValueError("cached identity/content differs")
        except (ValueError, KeyError, TypeError, AttributeError) as error:
            raise ArtifactConflictError(f"artifact conflict: {path}") from error
        return path, cached, True

    if path.exists():
        return reuse()
    output_dir.mkdir(parents=True, exist_ok=True)
    bundle = {"result": result, "run": run.model_dump(mode="json")}
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=output_dir, delete=False) as staged:
        temporary = Path(staged.name)
        try:
            json.dump(bundle, staged, ensure_ascii=False, indent=2)
            staged.flush()
            os.fsync(staged.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.link(temporary, path)
    except FileExistsError:
        return reuse()
    finally:
        temporary.unlink(missing_ok=True)
    return path, bundle, False
