import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from catchain.domain import ParsedDocument, ParsedPage, Registry
from catchain.extraction.llm.contract import ground_response, select_pages
from catchain.parsing.quality import measure_text_quality


def document(texts):
    return ParsedDocument(
        document_version_id=uuid4(), parser_name="test", parser_version="1",
        created_at=datetime.now(UTC), pages=tuple(
            ParsedPage(page_number=i, text=text, char_start=0, char_end=len(text),
                       quality=measure_text_quality(text))
            for i, text in enumerate(texts, 1)
        ),
    )


def response(quote="Installed capacity: 12 MW", page=1):
    return {"observations": [{
        "field_name": "installed_capacity_mw", "raw_value": "12 MW",
        "normalized_value": 12, "unit": "MW", "missing_reason": None,
        "evidence": [{"page_number": page, "quote": quote}],
    }]}


def ground(parsed, payload):
    return ground_response(
        json.dumps(payload), parsed, selected_page_numbers=(1,),
        requested_fields=("installed_capacity_mw",), project_id="VCS1",
        registry=Registry.VERRA, pipeline_run_id=uuid4(), extractor_name="offline-fixture",
        extractor_version="1",
    )


def test_grounding_uses_trusted_identity_and_exact_source_offsets():
    parsed = document(("Title\nInstalled capacity: 12 MW\n",))
    result = ground(parsed, response())
    observation = result.observations[0]
    evidence = observation.evidence[0]
    assert evidence.document_version_id == parsed.document_version_id
    assert parsed.pages[0].text[evidence.char_start:evidence.char_end] == evidence.quote
    assert observation.validation_status == "unvalidated"
    assert observation.confidence is None
    assert result.pipeline_run_id is not None


@pytest.mark.parametrize("payload", [response("Capacity: 99 MW"), response(page=2)])
def test_reject_invented_or_unselected_evidence(payload):
    with pytest.raises(ValueError):
        ground(document(("Installed capacity: 12 MW", "Installed capacity: 12 MW")), payload)


def test_reject_ambiguous_quote_and_unknown_field_or_identity():
    with pytest.raises(ValueError, match="ambiguous"):
        ground(document(("Installed capacity: 12 MW\nInstalled capacity: 12 MW",)), response())
    payload = response()
    payload["project_id"] = "invented"
    with pytest.raises(ValidationError):
        ground(document(("Installed capacity: 12 MW",)), payload)
    payload = response()
    payload["observations"][0]["field_name"] = "country"
    with pytest.raises(ValueError, match="exactly requested"):
        ground(document(("Installed capacity: 12 MW",)), payload)


def test_abstention_is_not_a_value_and_missing_field_is_rejected():
    payload = response()
    item = payload["observations"][0]
    item.update(raw_value=None, normalized_value=None, evidence=[], missing_reason="not_found")
    assert ground(document(("No capacity stated",)), payload).observations[0].missing_reason
    item["normalized_value"] = 12
    with pytest.raises(ValidationError):
        ground(document(("No capacity stated",)), payload)
    with pytest.raises(ValidationError):
        ground(document(("Text",)), {"observations": []})


def test_page_selection_is_deterministic_bounded_and_never_truncates():
    parsed = document(("one", "two"))
    assert [page.page_number for page in select_pages(parsed, (2, 1))] == [1, 2]
    for selection in [(), (1, 1), (0,), (3,), (True,)]:
        with pytest.raises(ValueError):
            select_pages(parsed, selection)
    with pytest.raises(ValueError, match="page budget"):
        select_pages(parsed, (1, 2), max_pages=1)
    with pytest.raises(ValueError, match="character budget"):
        select_pages(parsed, (1, 2), max_characters=5)
    with pytest.raises(ValueError, match="no text"):
        select_pages(document((" ",)), (1,))
