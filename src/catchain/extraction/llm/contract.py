"""Provider-neutral boundary: models supply values/quotes, never trusted identities."""

from datetime import UTC, datetime
from typing import Literal, Protocol
from uuid import UUID

from pydantic import Field, StrictInt, StrictStr, model_validator

from catchain.domain.common import ImmutableDomainModel
from catchain.domain.documents import Registry
from catchain.domain.evidence import EvidenceRef
from catchain.domain.extraction import (
    CandidateValue,
    FieldName,
    FieldObservation,
    ProjectExtraction,
)
from catchain.domain.parsing import ParsedDocument, ParsedPage
from catchain.extraction.llm.providers import ProviderReply


class ModelQuote(ImmutableDomainModel):
    page_number: StrictInt = Field(ge=1)
    quote: StrictStr = Field(min_length=1)


class ModelObservation(ImmutableDomainModel):
    field_name: FieldName
    raw_value: StrictStr | None = Field(min_length=1)
    normalized_value: CandidateValue | None
    unit: StrictStr | None = Field(min_length=1)
    evidence: tuple[ModelQuote, ...]
    missing_reason: Literal["not_found", "ambiguous"] | None

    @model_validator(mode="after")
    def check_candidate(self):
        if self.missing_reason is None:
            if self.raw_value is None or self.normalized_value is None or not self.evidence:
                raise ValueError("candidate requires values and evidence")
        elif self.raw_value is not None or self.normalized_value is not None:
            raise ValueError("abstention cannot carry values")
        return self


class ModelResponse(ImmutableDomainModel):
    observations: tuple[ModelObservation, ...] = Field(min_length=1)


class StructuredProvider(Protocol):
    """Adapter returns raw JSON; the workflow validates it independently."""

    name: str
    model: str

    def extract(
        self, *, system_prompt: str, input_json: str, max_output_tokens: int
    ) -> ProviderReply: ...


def select_pages(
    parsed: ParsedDocument,
    page_numbers: tuple[int, ...],
    *,
    max_pages: int = 8,
    max_characters: int = 24000,
) -> tuple[ParsedPage, ...]:
    """Explicit, sorted whole pages; fail rather than silently truncate source text."""
    if max_pages < 1 or max_characters < 1:
        raise ValueError("page and character budgets must be positive")
    if not page_numbers or len(set(page_numbers)) != len(page_numbers):
        raise ValueError("select nonempty, unique pages")
    if any(
        type(number) is not int or not 1 <= number <= len(parsed.pages) for number in page_numbers
    ):
        raise ValueError("selected page is outside document")
    if len(page_numbers) > max_pages:
        raise ValueError("page budget exceeded")
    pages = tuple(parsed.pages[number - 1] for number in sorted(page_numbers))
    if sum(len(page.text) for page in pages) > max_characters:
        raise ValueError("character budget exceeded")
    if not any(page.text.strip() for page in pages):
        raise ValueError("selected pages contain no text")
    return pages


def ground_response(
    response_json: str,
    parsed: ParsedDocument,
    *,
    selected_page_numbers: tuple[int, ...],
    requested_fields: tuple[FieldName, ...],
    project_id: str,
    registry: Registry,
    pipeline_run_id: UUID,
    extractor_name: str,
    extractor_version: str,
) -> ProjectExtraction:
    """Reject missing coverage and invented quotes; keep semantics unvalidated."""
    if not requested_fields or len(set(requested_fields)) != len(requested_fields):
        raise ValueError("request nonempty, unique fields")
    pages = {page.page_number: page for page in select_pages(parsed, selected_page_numbers)}
    response = ModelResponse.model_validate_json(response_json)
    if {item.field_name for item in response.observations} != set(requested_fields):
        raise ValueError("response must cover exactly requested fields")
    observations = []
    for item in response.observations:
        evidence = []
        for quote in item.evidence:
            if quote.page_number not in pages:
                raise ValueError("evidence points to an unselected page")
            text = pages[quote.page_number].text
            start = text.find(quote.quote)
            if start < 0:
                raise ValueError("evidence quote is absent from selected page")
            if text.find(quote.quote, start + 1) >= 0:
                raise ValueError("evidence quote location is ambiguous; use a longer quote")
            evidence.append(
                EvidenceRef(
                    document_version_id=parsed.document_version_id,
                    page_number=quote.page_number,
                    quote=quote.quote,
                    char_start=start,
                    char_end=start + len(quote.quote),
                )
            )
        observations.append(
            FieldObservation(
                field_name=item.field_name,
                raw_value=item.raw_value,
                normalized_value=item.normalized_value,
                unit=item.unit,
                evidence=tuple(evidence),
                missing_reason=item.missing_reason,
                issues=("semantic_validation_pending", "selected_pages_only"),
            )
        )
    return ProjectExtraction(
        project_id=project_id,
        registry=registry,
        document_version_id=parsed.document_version_id,
        parsed_document_id=parsed.parsed_document_id,
        extractor_name=extractor_name,
        extractor_version=extractor_version,
        pipeline_run_id=pipeline_run_id,
        created_at=datetime.now(UTC),
        observations=tuple(observations),
    )
