"""Deterministic, bounded-memory dataset sampling."""

import hashlib
import heapq
import json
import os
from pathlib import Path

from catchain.dataset.manifest import iter_manifest_rows
from catchain.dataset.models import DatasetManifestHeader, ManifestRow, SampledManifestRow


def _rank(seed: int, relative_path: str) -> int:
    value = f"{seed}:{relative_path}".encode()
    return int.from_bytes(hashlib.sha256(value).digest()[:8], "big")


def sample_manifest(
    manifest: Path,
    output: Path,
    *,
    development: int,
    validation: int,
    test: int,
    seed: int = 0,
) -> dict[str, int]:
    """Select deterministic rows without loading all manifest rows into memory."""
    requested = {"development": development, "validation": validation, "test": test}
    if any(value < 0 for value in requested.values()) or sum(requested.values()) == 0:
        raise ValueError("sample counts must be non-negative and at least one must be positive")
    total = sum(requested.values())
    heap: list[tuple[int, str, ManifestRow]] = []
    for row in iter_manifest_rows(manifest):
        item = (-_rank(seed, row.relative_path), row.relative_path, row)
        if len(heap) < total:
            heapq.heappush(heap, item)
        elif item > heap[0]:
            heapq.heapreplace(heap, item)
    if len(heap) < total:
        raise ValueError(f"manifest has {len(heap)} rows but {total} samples were requested")
    selected = sorted(
        (item[2] for item in heap),
        key=lambda row: (_rank(seed, row.relative_path), row.relative_path),
    )
    assignments: list[SampledManifestRow] = []
    offset = 0
    counts: dict[str, int] = {}
    for split, count in requested.items():
        for row in selected[offset : offset + count]:
            assignments.append(
                SampledManifestRow(
                    **row.model_dump(exclude={"sample_split"}), sample_split=split
                )
            )
        counts[split] = count
        offset += count
    output.parent.mkdir(parents=True, exist_ok=True)
    header = DatasetManifestHeader.model_validate_json(
        manifest.read_text(encoding="utf-8").splitlines()[0]
    )
    temporary = output.with_suffix(output.suffix + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            sampled_header = header.model_copy(
                update={
                    "row_count": len(assignments),
                    "total_bytes": sum(row.size_bytes for row in assignments),
                }
            )
            stream.write(
                json.dumps(sampled_header.model_dump(mode="json"), ensure_ascii=False) + "\n"
            )
            for row in assignments:
                stream.write(json.dumps(row.model_dump(mode="json"), ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, output)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return counts

