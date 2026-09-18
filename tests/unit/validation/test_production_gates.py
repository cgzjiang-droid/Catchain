from uuid import uuid4

import pytest

from catchain.validation.production_gates import require_version_reprocess


def test_new_document_version_requires_all_reprocessing_stages() -> None:
    gate = require_version_reprocess(
        previous_document_version_id=uuid4(),
        current_document_version_id=uuid4(),
        completed_stages=("parsed", "extracted"),
    )

    assert gate.missing_stages == ("validated", "reviewed")
    assert gate.eligible_for_canonical_promotion is False


def test_same_version_cannot_be_called_a_reprocess() -> None:
    version = uuid4()
    with pytest.raises(ValueError, match="newer"):
        require_version_reprocess(
            previous_document_version_id=version,
            current_document_version_id=version,
            completed_stages=("parsed", "extracted", "validated", "reviewed"),
        )

