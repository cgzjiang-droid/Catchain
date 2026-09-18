"""Load only authority-backed, approved scoring policies."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from catchain.domain.policy import ScoringPolicy


class PolicyBlocked(ValueError):
    """Raised when a draft or incomplete policy is used for production scoring."""


@dataclass(frozen=True, slots=True)
class ApprovedPolicy:
    policy: ScoringPolicy
    sha256: str
    source_path: Path


def load_approved_policy(path: Path) -> ApprovedPolicy:
    raw = Path(path).read_bytes()
    policy = ScoringPolicy.model_validate_json(raw)
    if policy.status != "approved":
        raise PolicyBlocked("scoring policy is not approved")
    return ApprovedPolicy(
        policy=policy,
        sha256=hashlib.sha256(raw).hexdigest(),
        source_path=Path(path),
    )

