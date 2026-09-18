from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from catchain.domain import EvidenceRef, GoldFieldLabel, GoldSample, Registry


def test_confirmed_gold_requires_value_and_locatable_evidence():
    with pytest.raises(ValidationError):
        GoldFieldLabel(field_name="project_name", status="confirmed", reason="reviewed")


def test_gold_freeze_requires_adjudication_and_resolves_conflicts():
    document_version_id = uuid4()
    evidence = EvidenceRef(
        document_version_id=document_version_id,
        page_number=1,
        quote="Solar project",
        char_start=0,
        char_end=13,
    )
    confirmed = GoldFieldLabel(
        field_name="project_name",
        status="confirmed",
        value="Solar project",
        evidence=(evidence,),
        reason="Two reviewers agreed on the project name",
    )
    base = dict(
        dataset_version="gold-v1",
        sample_id="acr-vcs1",
        split="validation",
        registry=Registry.ACR,
        project_id="VCS1",
        document_version_id=document_version_id,
        parsed_document_id=uuid4(),
        labels=(confirmed,),
        reviewers=("reviewer-a", "reviewer-b"),
    )
    with pytest.raises(ValidationError):
        GoldSample(**base, status="frozen")
    frozen = GoldSample(
        **base,
        status="frozen",
        adjudicator="team-lead",
        frozen_at=datetime.now(UTC),
    )
    assert frozen.status == "frozen"

    conflict = GoldFieldLabel(
        field_name="project_name",
        status="conflicting",
        reason="Reviewers supplied different names",
    )
    with pytest.raises(ValidationError):
        GoldSample(**{**base, "labels": (conflict,)}, status="frozen", adjudicator="lead")
    draft = GoldSample(
        **{**base, "labels": (conflict,)}, status="adjudication_required"
    )
    assert draft.status == "adjudication_required"
