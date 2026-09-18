from datetime import UTC, datetime, timedelta

from catchain.jobs import JobKind, JobStatus, JobStore, RetryPolicy
from catchain.storage.database import create_schema, create_sqlite_engine


def test_job_enqueue_is_idempotent_and_failure_resumes(tmp_path) -> None:
    engine = create_sqlite_engine(tmp_path / "jobs.sqlite")
    create_schema(engine)
    store = JobStore(engine)

    first = store.enqueue(kind=JobKind.PARSE, input_identity="doc:v1", payload={"page": 1})
    duplicate = store.enqueue(kind=JobKind.PARSE, input_identity="doc:v1", payload={"page": 1})
    assert duplicate.job_id == first.job_id

    claimed = store.claim_next(now=datetime.now(UTC))
    assert claimed is not None and claimed.status == JobStatus.RUNNING
    failed = store.mark_failed(
        claimed,
        error_code="timeout",
        error_message="temporary",
        policy=RetryPolicy(base_delay_seconds=0),
        now=datetime.now(UTC),
    )
    assert failed.status == JobStatus.RETRY
    resumed = store.claim_next(now=datetime.now(UTC) + timedelta(seconds=1))
    assert resumed is not None and resumed.job_id == first.job_id
    store.mark_succeeded(resumed.job_id)
    assert store.claim_next(now=datetime.now(UTC)) is None

