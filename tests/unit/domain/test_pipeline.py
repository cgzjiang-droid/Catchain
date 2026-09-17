from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

import catchain.domain as domain

STARTED = datetime(2026, 9, 9, 8, 0, tzinfo=UTC)


def test_succeeded_pipeline_run_has_finish_time_and_no_error() -> None:
    run = domain.PipelineRun(
        stage=domain.PipelineStage.HASHED,
        status=domain.RunStatus.SUCCEEDED,
        input_hash="a" * 64,
        config_hash="b" * 64,
        started_at=STARTED,
        finished_at=STARTED + timedelta(seconds=2),
    )

    assert run.status is domain.RunStatus.SUCCEEDED
    assert run.error_code is None


def test_failed_pipeline_run_requires_typed_error() -> None:
    with pytest.raises(ValidationError, match="failed run requires"):
        domain.PipelineRun(
            stage=domain.PipelineStage.PARSED,
            status=domain.RunStatus.FAILED,
            input_hash="a" * 64,
            config_hash="b" * 64,
            started_at=STARTED,
            finished_at=STARTED + timedelta(seconds=1),
        )


def test_pipeline_run_rejects_finish_before_start() -> None:
    with pytest.raises(ValidationError, match="before started_at"):
        domain.PipelineRun(
            stage=domain.PipelineStage.DOWNLOADED,
            status=domain.RunStatus.SUCCEEDED,
            input_hash="a" * 64,
            config_hash="b" * 64,
            started_at=STARTED,
            finished_at=STARTED - timedelta(seconds=1),
        )


def test_running_pipeline_run_rejects_finish_time() -> None:
    with pytest.raises(ValidationError, match="running run cannot have finished_at"):
        domain.PipelineRun(
            stage=domain.PipelineStage.DOWNLOADED,
            status=domain.RunStatus.RUNNING,
            input_hash="a" * 64,
            config_hash="b" * 64,
            started_at=STARTED,
            finished_at=STARTED + timedelta(seconds=1),
        )


def test_completed_pipeline_run_requires_finish_time() -> None:
    with pytest.raises(ValidationError, match="completed run requires finished_at"):
        domain.PipelineRun(
            stage=domain.PipelineStage.HASHED,
            status=domain.RunStatus.SUCCEEDED,
            input_hash="a" * 64,
            config_hash="b" * 64,
            started_at=STARTED,
        )


def test_succeeded_pipeline_run_rejects_error_details() -> None:
    with pytest.raises(ValidationError, match="only failed run may contain error details"):
        domain.PipelineRun(
            stage=domain.PipelineStage.HASHED,
            status=domain.RunStatus.SUCCEEDED,
            input_hash="a" * 64,
            config_hash="b" * 64,
            started_at=STARTED,
            finished_at=STARTED + timedelta(seconds=1),
            error_code="UNEXPECTED",
            error_message="This run should not carry errors.",
        )
