from datetime import UTC, datetime
from uuid import uuid4

import pytest

from catchain.domain import ParsedDocument, ParsedPage
from catchain.parsing.quality import measure_text_quality
from catchain.scoring.keyword_baseline import score_keywords


def document(*texts):
    return ParsedDocument(
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


def test_keyword_thresholds_grounding_and_known_denial_limitation():
    for text, score in (
        ("", 0),
        ("scope", 1),
        ("GRID-CONNECTED", 2),
        ("grid-connected project boundary applicability", 3),
    ):
        assert score_keywords((document(text),))["dimensions"][0]["score"] == score
    denial = "Not grid-connected. Project boundary undefined; applicability not established."
    first = document("unrelated", denial)
    second = document(denial)
    result = score_keywords((first, second))
    d01 = result["dimensions"][0]
    assert d01["score"] == 3  # Legacy keyword behavior, not a semantic judgment.
    assert d01["hit_count_high"] == 3
    assert len(d01["evidence"]) == 3
    for e in d01["evidence"]:
        assert e["document_version_id"] == str(first.document_version_id)
        assert e["page_number"] == 2
        assert denial[e["char_start"] : e["char_end"]] == e["quote"]
    assert len(result["dimensions"]) == 12
    assert result["max_score"] == 36
    assert result["keyword_score_ratio"] == result["total_score"] / 36
    assert "coverage_ratio" not in result
    assert score_keywords((document(denial * 4),))["dimensions"][0]["hit_count_high"] == 3
    assert (
        score_keywords((document("project", "boundary"),))["dimensions"][0]["hit_count_high"] == 0
    )
    with pytest.raises(ValueError):
        score_keywords(())
