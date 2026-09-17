from datetime import UTC, datetime
from uuid import uuid4

from catchain.domain import ParsedDocument, ParsedPage, Registry
from catchain.extraction.baseline.regex import extract_regex
from catchain.parsing.quality import measure_text_quality


def test_regex_preserves_candidates_page_evidence_and_missing_reasons():
    texts = (
        "Host country: Brazil\nInstalled capacity: 12.5 MW\nER: 1,234.5\n",
        "Installed capacity: 14 MW\nVerifier: Example Audit\nACM0002\n",
    )
    parsed = ParsedDocument(
        document_version_id=uuid4(),
        parser_name="test",
        parser_version="1",
        created_at=datetime.now(UTC),
        pages=tuple(
            ParsedPage(
                page_number=i,
                text=t,
                char_start=0,
                char_end=len(t),
                quality=measure_text_quality(t),
            )
            for i, t in enumerate(texts, 1)
        ),
    )
    result = extract_regex(parsed, "VCS7", Registry.VERRA, pipeline_run_id=uuid4())
    capacities = [o for o in result.observations if o.field_name == "installed_capacity_mw"]
    assert [o.normalized_value for o in capacities] == [12.5, 14.0]
    assert [o.evidence[0].page_number for o in capacities] == [1, 2]
    by_name = {o.field_name: o for o in result.observations}
    assert by_name["country"].normalized_value == "Brazil"
    assert by_name["verifier_name"].normalized_value == "Example Audit"
    assert by_name["methodology_name"].normalized_value == "ACM0002"
    assert by_name["er_reported_tco2e"].normalized_value == 1234.5
    assert "unit_not_verified" in by_name["er_reported_tco2e"].issues
    assert by_name["validator_name"].missing_reason == "not_found"
    assert by_name["registered_date"].missing_reason == "unsupported_by_baseline"
    assert by_name["project_name"].normalized_value is None
    assert len(by_name) == 55
    for observation in result.observations:
        assert observation.confidence is None
        for evidence in observation.evidence:
            text = texts[evidence.page_number - 1]
            assert text[evidence.char_start : evidence.char_end] == evidence.quote
            assert evidence.document_version_id == parsed.document_version_id
    assert result.parsed_document_id == parsed.parsed_document_id


def test_business_candidates_preserve_roles_and_ambiguous_dates():
    texts = (
        "Project title: Example Wind Project\nProject owner: Alpha & Beta Ltd\n"
        "Project developer: Delta Ltd\nProject participant: First Ltd / Second Ltd\n"
        "Crediting period: 7 years\nCrediting period start: 03/04/2020\n",
        "Project owner: Gamma Ltd\nCrediting period end: 2027\n"
        "Crediting period start: 2020-03-04\nSGS prepared this report\n",
    )
    parsed = ParsedDocument(
        document_version_id=uuid4(),
        parser_name="test",
        parser_version="1",
        created_at=datetime.now(UTC),
        pages=tuple(
            ParsedPage(
                page_number=i,
                text=text,
                char_start=0,
                char_end=len(text),
                quality=measure_text_quality(text),
            )
            for i, text in enumerate(texts, 1)
        ),
    )
    run_id = uuid4()
    result = extract_regex(parsed, "VCS7", Registry.VERRA, pipeline_run_id=run_id)
    assert result.pipeline_run_id == run_id
    owners = [o for o in result.observations if o.field_name == "project_owner"]
    assert [o.normalized_value for o in owners] == ["Alpha & Beta Ltd", "Gamma Ltd"]
    by_name = {o.field_name: o for o in result.observations}
    assert by_name["project_name"].normalized_value == "Example Wind Project"
    assert by_name["project_developer"].normalized_value == "Delta Ltd"
    assert by_name["project_participant"].raw_value == "First Ltd / Second Ltd"
    assert by_name["crediting_period_years"].normalized_value == 7
    starts = [o for o in result.observations if o.field_name == "crediting_period_start"]
    assert starts[0].raw_value == "03/04/2020"
    assert "ambiguous_numeric_date" in starts[0].issues
    assert starts[1].raw_value == "2020-03-04"
    assert "year_only_date" not in starts[1].issues
    assert by_name["crediting_period_end"].normalized_value == "2027"
    assert "year_only_date" in by_name["crediting_period_end"].issues
    assert by_name["verifier_name"].normalized_value is None
    assert result.schema_version == "1.1.0"
    for observation in result.observations:
        assert observation.validation_status == "unvalidated"
        for e in observation.evidence:
            assert texts[e.page_number - 1][e.char_start : e.char_end] == e.quote
