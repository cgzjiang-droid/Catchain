from catchain.jobs.retry import RetryPolicy


def test_retry_policy_is_bounded_and_classifies_permanent_errors() -> None:
    policy = RetryPolicy(max_attempts=3, base_delay_seconds=10, max_delay_seconds=100)

    assert policy.next_attempt(attempt=0, error_code="timeout").delay_seconds == 10
    assert policy.next_attempt(attempt=2, error_code="timeout").retry is True
    assert policy.next_attempt(attempt=3, error_code="timeout").reason == "max_attempts_exceeded"
    assert policy.next_attempt(attempt=0, error_code="invalid_pdf").retry is False

