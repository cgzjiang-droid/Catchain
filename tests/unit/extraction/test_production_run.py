from datetime import UTC, datetime
from uuid import uuid4

from catchain.domain import ParsedDocument, ParsedPage, Registry
from catchain.extraction.llm.contract import ground_response
from catchain.extraction.production_run import validate_grounding
from catchain.parsing.quality import measure_text_quality


def test_validate_grounding_rechecks_persisted_offsets() -> None:
    parsed = ParsedDocument(
        document_version_id=uuid4(),
        parser_name="test",
        parser_version="1",
        created_at=datetime.now(UTC),
        pages=(
            ParsedPage(
                page_number=1,
                text="Capacity: 12 MW",
                char_start=0,
                char_end=15,
                quality=measure_text_quality("Capacity: 12 MW"),
            ),
        ),
    )
    extraction = ground_response(
        '{"observations":[{"field_name":"installed_capacity_mw","raw_value":"12 MW",'
        '"normalized_value":12,"unit":"MW","missing_reason":null,'
        '"evidence":[{"page_number":1,"quote":"Capacity: 12 MW"}]}]}',
        parsed,
        selected_page_numbers=(1,),
        requested_fields=("installed_capacity_mw",),
        project_id="VCS-1",
        registry=Registry.VERRA,
        pipeline_run_id=uuid4(),
        extractor_name="test",
        extractor_version="1",
    )

    report = validate_grounding(extraction, parsed)

    assert report.valid is True
    assert report.checked_evidence == 1

