"""Bind explicit rubric judgments to current approved inputs and exact source text."""

import hashlib
import json
from importlib.resources import files

from catchain.domain import PipelineRun, PipelineStage, Registry, RunStatus
from catchain.domain.judgment import JudgmentRequest
from catchain.scoring.readiness import project_readiness
from catchain.storage.document_repository import SqlAlchemyDocumentRepository


def grounded_judgments(engine, bundle: dict, request: JudgmentRequest) -> dict:
    request = JudgmentRequest.model_validate_json(request.model_dump_json())
    readiness = bundle["result"]
    run = PipelineRun.model_validate(bundle["run"])
    stable = {k: v for k, v in readiness.items() if k != "pipeline_run_id"}
    current = project_readiness(
        engine, registry=Registry(readiness["registry"]), project_id=readiness["project_id"]
    )
    if (
        run.stage != PipelineStage.EVALUATED
        or run.status != RunStatus.SUCCEEDED
        or readiness["pipeline_run_id"] != str(run.pipeline_run_id)
        or run.input_hash != hashlib.sha256(json.dumps(stable, sort_keys=True).encode()).hexdigest()
        or run.config_hash != current["rules_sha256"]
        or stable != current
    ):
        raise ValueError("stale or modified readiness")
    raw = files("catchain.scoring").joinpath(request.rubric_version + ".json").read_bytes()
    rubric = json.loads(raw)
    rules = {c["criterion_id"]: d for d in rubric["dimensions"] for c in d["criteria"]}
    facts = {f["fact_id"]: (name, f) for name, f in current["facts"].items()}
    documents = SqlAlchemyDocumentRepository(engine)
    for judgment in request.judgments:
        rule = rules.get(judgment.criterion_id)
        if rule is None:
            raise ValueError("unknown criterion")
        selected = []
        allowed = set(rule["input_fields"]) | {"methodology_name", "methodology_version"}
        if rule["dimension_id"] == "D08":
            allowed |= {"pe_value_tco2e", "le_value_tco2e"}
        for fact_id in judgment.fact_ids:
            item = facts.get(str(fact_id))
            if item is None or item[0] not in allowed:
                raise ValueError("fact absent or outside dimension scope")
            selected.append(item[1])
        for ref in judgment.evidence:
            matches = [
                f for f in selected if f["document_version_id"] == str(ref.document_version_id)
            ]
            texts = [
                p.text
                for f in matches
                for p in documents.get_parsed(f["parsed_document_id"]).pages
                if p.page_number == ref.page_number
            ]
            if (
                ref.char_start is None
                or ref.char_end is None
                or not ref.quote.strip()
                or not any(
                    ref.char_end <= len(t) and t[ref.char_start : ref.char_end] == ref.quote
                    for t in texts
                )
            ):
                raise ValueError("judgment evidence not grounded in referenced facts")
    covered = {j.criterion_id for j in request.judgments}
    return {
        "schema_version": "1.0.0",
        "rubric_version": request.rubric_version,
        "rubric_sha256": hashlib.sha256(raw).hexdigest(),
        "rubric_status": rubric["status"],
        "request": request.model_dump(mode="json"),
        "input_readiness": readiness,
        "unreviewed_criteria": sorted(set(rules) - covered),
        "total_score": None,
        "model_calls": 0,
        "limitations": [
            "human_asserted_semantics",
            "local_reviewer_not_authenticated",
            "draft_rubric_no_scores",
        ],
    }
