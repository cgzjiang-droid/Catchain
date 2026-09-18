"""Finite retry decisions for external and document-processing failures."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RetryDecision:
    retry: bool
    delay_seconds: int
    reason: str


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_seconds: int = 30
    max_delay_seconds: int = 3600

    def next_attempt(self, *, attempt: int, error_code: str) -> RetryDecision:
        if attempt >= self.max_attempts:
            return RetryDecision(False, 0, "max_attempts_exceeded")
        if error_code in {"invalid_pdf", "schema_invalid", "evidence_missing", "permission_denied"}:
            return RetryDecision(False, 0, "permanent_error")
        delay = min(self.max_delay_seconds, self.base_delay_seconds * (2**attempt))
        return RetryDecision(True, delay, "transient_error")

