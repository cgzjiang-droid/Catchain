"""Persist versioned evaluation result payloads beside their processing run."""

import json

from sqlalchemy import insert, select

from catchain.domain import PipelineRun
from catchain.storage.database import evaluation_results, processing_runs


def store_evaluation_result(engine, result: dict, run: PipelineRun) -> dict:
    """Store one immutable result, or return the identical existing row."""

    run_id = str(run.pipeline_run_id)
    payload = json.dumps(result, ensure_ascii=False, sort_keys=True)
    with engine.connect() as connection:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            existing = connection.execute(
                select(evaluation_results).where(evaluation_results.c.pipeline_run_id == run_id)
            ).mappings().one_or_none()
            if existing is not None:
                if existing["payload_json"] != payload:
                    raise ValueError("evaluation result identity conflict")
                connection.commit()
                return {
                    "status": "reused",
                    "evaluation_result_id": existing["evaluation_result_id"],
                }
            connection.execute(
                insert(processing_runs).values(
                    pipeline_run_id=run_id,
                    payload_json=run.model_dump_json(),
                )
            )
            evaluation_result_id = run_id
            connection.execute(
                insert(evaluation_results).values(
                    evaluation_result_id=evaluation_result_id,
                    pipeline_run_id=run_id,
                    registry=result["input_readiness"]["registry"],
                    project_id=result["input_readiness"]["project_id"],
                    rubric_version=result["rubric_version"],
                    rubric_sha256=result["rubric_sha256"],
                    score_status=result["score_status"],
                    total_score=result["total_score"],
                    payload_json=payload,
                )
            )
            connection.commit()
            return {"status": "stored", "evaluation_result_id": evaluation_result_id}
        except BaseException:
            connection.rollback()
            raise
