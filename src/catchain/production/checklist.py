"""Deterministic production readiness checks."""

from collections.abc import Mapping

from catchain.domain.production import ProductionCheck, ProductionChecklist

_REQUIRED = {
    "real_gold": "A frozen human Gold dataset is available.",
    "approved_policy": "An approved scoring policy with authority evidence is available.",
    "registry_sync": "Registry adapters and an incremental sync checkpoint are available.",
    "production_storage": "PostgreSQL and immutable object storage are configured.",
    "review_api": "The authenticated review API is deployed.",
    "observability": "Health checks, structured logs, metrics and alerts are configured.",
}


def production_checklist(evidence: Mapping[str, bool]) -> ProductionChecklist:
    checks = []
    blockers = []
    for code, description in _REQUIRED.items():
        if evidence.get(code) is True:
            checks.append(ProductionCheck(code=code, status="pass", evidence=description))
        else:
            checks.append(
                ProductionCheck(
                    code=code,
                    status="blocked",
                    evidence=f"Missing: {description}",
                )
            )
            blockers.append(code)
    return ProductionChecklist(
        status="ready" if not blockers else "blocked",
        checks=tuple(checks),
        blockers=tuple(blockers),
    )

