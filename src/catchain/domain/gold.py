"""Human-gold contracts; model outputs can never become frozen labels automatically."""

from typing import Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, Field, StrictStr, model_validator

from catchain.domain.common import ImmutableDomainModel
from catchain.domain.documents import Registry
from catchain.domain.evidence import EvidenceRef
from catchain.domain.extraction import CandidateValue, FieldName


class GoldFieldLabel(ImmutableDomainModel):
    field_name: FieldName
    status: Literal["confirmed", "unknown", "conflicting"]
    value: CandidateValue | None = None
    unit: StrictStr | None = None
    evidence: tuple[EvidenceRef, ...] = ()
    reason: StrictStr = Field(min_length=1)

    @model_validator(mode="after")
    def validate_label(self) -> Self:
        if not self.reason.strip():
            raise ValueError("gold label reason cannot be blank")
        if self.status == "confirmed" and (self.value is None or not self.evidence):
            raise ValueError("confirmed gold labels need a value and evidence")
        if self.status != "confirmed" and (self.value is not None or self.evidence):
            raise ValueError("unknown or conflicting labels cannot carry a chosen value")
        return self


class GoldSample(ImmutableDomainModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    dataset_version: StrictStr = Field(min_length=1)
    sample_id: StrictStr = Field(min_length=1)
    split: Literal["development", "validation", "test"]
    registry: Registry
    project_id: StrictStr = Field(min_length=1)
    document_version_id: UUID
    parsed_document_id: UUID
    labels: tuple[GoldFieldLabel, ...] = Field(min_length=1)
    reviewers: tuple[StrictStr, ...] = Field(min_length=1)
    status: Literal["draft", "adjudication_required", "frozen"] = "draft"
    adjudicator: StrictStr | None = None
    frozen_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_freeze(self) -> Self:
        if len({label.field_name for label in self.labels}) != len(self.labels):
            raise ValueError("gold sample cannot contain duplicate fields")
        if any(not reviewer.strip() for reviewer in self.reviewers):
            raise ValueError("reviewer cannot be blank")
        conflicts = any(label.status == "conflicting" for label in self.labels)
        if self.status == "adjudication_required" and not conflicts:
            raise ValueError("adjudication_required needs a conflicting label")
        if self.status == "frozen":
            if len(self.reviewers) < 2:
                raise ValueError("frozen gold requires two reviewers")
            if not self.adjudicator or not self.adjudicator.strip() or self.frozen_at is None:
                raise ValueError("frozen gold requires an adjudicator and timestamp")
            if conflicts:
                raise ValueError("frozen gold cannot retain conflicting labels")
        return self


class GoldDataset(ImmutableDomainModel):
    """A split manifest that prevents the same project leaking across evaluation sets."""

    schema_version: Literal["1.0.0"] = "1.0.0"
    dataset_version: StrictStr = Field(min_length=1)
    samples: tuple[GoldSample, ...] = Field(min_length=1)
    status: Literal["draft", "frozen"] = "draft"
    frozen_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_manifest(self) -> Self:
        if len({sample.sample_id for sample in self.samples}) != len(self.samples):
            raise ValueError("GoldDataset cannot contain duplicate sample ids")
        if any(sample.dataset_version != self.dataset_version for sample in self.samples):
            raise ValueError("GoldSample dataset version differs from manifest")
        project_splits: dict[str, str] = {}
        for sample in self.samples:
            previous = project_splits.setdefault(sample.project_id, sample.split)
            if previous != sample.split:
                raise ValueError("a project cannot appear in multiple dataset splits")
        if self.status == "frozen":
            if self.frozen_at is None:
                raise ValueError("frozen GoldDataset requires a timestamp")
            if any(sample.status != "frozen" for sample in self.samples):
                raise ValueError("frozen GoldDataset requires frozen samples")
        return self
