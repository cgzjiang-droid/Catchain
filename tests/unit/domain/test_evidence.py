from uuid import uuid4

import pytest
from pydantic import ValidationError

import catchain.domain as domain


def test_evidence_uses_one_based_page_and_optional_offsets() -> None:
    evidence = domain.EvidenceRef(
        document_version_id=uuid4(),
        page_number=18,
        quote="Expected annual emission reductions are 120,000 tCO2e.",
        char_start=240,
        char_end=296,
    )

    assert evidence.page_number == 18
    assert evidence.char_end > evidence.char_start


@pytest.mark.parametrize(
    ("char_start", "char_end"),
    [(10, None), (None, 20), (20, 20), (21, 20)],
)
def test_evidence_rejects_incomplete_or_reversed_offsets(
    char_start: int | None,
    char_end: int | None,
) -> None:
    with pytest.raises(ValidationError):
        domain.EvidenceRef(
            document_version_id=uuid4(),
            page_number=1,
            quote="Source text",
            char_start=char_start,
            char_end=char_end,
        )


def test_evidence_rejects_zero_based_page() -> None:
    with pytest.raises(ValidationError):
        domain.EvidenceRef(
            document_version_id=uuid4(),
            page_number=0,
            quote="Source text",
        )
