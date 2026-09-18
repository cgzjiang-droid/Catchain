from uuid import uuid4

from catchain.validation.production_gates import require_version_reprocess


def test_new_version_does_not_become_promotable_until_review_is_completed() -> None:
    current = uuid4()
    gate = require_version_reprocess(
        previous_document_version_id=uuid4(),
        current_document_version_id=current,
        completed_stages=("parsed", "extracted", "validated"),
    )

    assert gate.current_document_version_id == current
    assert gate.eligible_for_canonical_promotion is False

