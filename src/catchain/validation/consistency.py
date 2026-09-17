"""Conservative local date/unit checks and project-level source disagreements."""

import json
import re
from datetime import date
from uuid import UUID

from catchain.domain.consistency import (
    CandidateLink,
    ConsistencyIssue,
    ProjectConsistencyReport,
    ValidationInput,
)

DATE_PAIRS = (
    ("crediting_period_start", "crediting_period_end"),
    ("verification_period_start", "verification_period_end"),
)
# Period-specific measurements/cycle dates are deliberately not treated as project invariants.
PROJECT_LEVEL_FIELDS = (
    "project_id",
    "project_name",
    "country",
    "installed_capacity_mw",
    "technology_type",
    "methodology_name",
    "methodology_version",
    "registered_date",
    "listed_date",
    "project_owner",
    "project_developer",
    "project_operator",
    "project_participant",
    "crediting_period_start",
    "crediting_period_end",
)


def validate_project(
    inputs: tuple[ValidationInput, ...],
    *,
    pipeline_run_id: UUID,
) -> ProjectConsistencyReport:
    if not inputs:
        raise ValueError("at least one validation input is required")
    inputs = tuple(sorted(inputs, key=lambda item: str(item.report.pipeline_run_id)))
    if len({item.report.pipeline_run_id for item in inputs}) != len(inputs):
        raise ValueError("duplicate validation inputs")
    project_id, registry = inputs[0].report.project_id, inputs[0].report.registry
    if any(
        (item.report.project_id, item.report.registry) != (project_id, registry) for item in inputs
    ):
        raise ValueError("cannot mix projects or registries")
    issues = []

    def add(code, fields, candidates, message):
        issues.append(
            ConsistencyIssue(
                code=code, fields=fields, candidates=tuple(candidates), message=message
            )
        )

    def active(item, field):
        return [
            (
                check.observation,
                CandidateLink(
                    validation_run_id=item.report.pipeline_run_id,
                    observation_index=check.observation_index,
                ),
            )
            for check in item.report.checks
            if check.observation.field_name == field
            and check.status != "rejected"
            and check.observation.missing_reason is None
        ]

    def unique(rows):
        values = {
            json.dumps([observation.normalized_value, observation.unit]) for observation, _ in rows
        }
        return rows[0][0] if len(values) == 1 else None

    for item in inputs:
        for start_field, end_field in DATE_PAIRS:
            starts, ends = active(item, start_field), active(item, end_field)
            start, end = unique(starts), unique(ends)
            if not starts and not ends:
                continue
            links = [link for _, link in starts + ends]
            if start is None or end is None:
                add(
                    "date_pair_incomplete_or_conflicting",
                    (start_field, end_field),
                    links,
                    "A unique start and end are required; do not combine unrelated candidates.",
                )
                continue
            dates = []
            for observation in (start, end):
                value = observation.normalized_value
                if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                    break
                try:
                    dates.append(date.fromisoformat(value))
                except ValueError:
                    break
            if len(dates) != 2:
                add(
                    "date_pair_not_evaluable",
                    (start_field, end_field),
                    links,
                    "Resolve date formats before comparing their order.",
                )
            elif dates[0] > dates[1]:
                add(
                    "date_order_reversed",
                    (start_field, end_field),
                    links,
                    "Start is after end; preserve both values for adjudication.",
                )
        for flag_field, value_field in (
            ("pe_applicable_flag", "pe_value_tco2e"),
            ("le_applicable_flag", "le_value_tco2e"),
        ):
            flags, values = active(item, flag_field), active(item, value_field)
            flag, value = unique(flags), unique(values)
            if (
                flag is not None
                and value is not None
                and flag.normalized_value is False
                and type(value.normalized_value) in (int, float)
                and value.normalized_value != 0
            ):
                add(
                    "applicability_value_difference",
                    (flag_field, value_field),
                    [link for _, link in flags + values],
                    "Not-applicable flag and nonzero value need context and period confirmation.",
                )
        generated = active(item, "electricity_generated_mwh")
        exported = active(item, "electricity_exported_mwh")
        first, second = unique(generated), unique(exported)
        if first is not None and second is not None and first.unit != second.unit:
            add(
                "energy_unit_difference",
                ("electricity_generated_mwh", "electricity_exported_mwh"),
                [link for _, link in generated + exported],
                "Confirm units and measurement periods before comparing energy values.",
            )
    methodologies = [row for item in inputs for row in active(item, "methodology_name")]
    if not methodologies or any(
        observation.normalized_value != "ACM0002" for observation, _ in methodologies
    ):
        add(
            "methodology_scope_unconfirmed",
            ("methodology_name",),
            [link for _, link in methodologies],
            "ACM0002 scope is not confirmed; do not apply an ACM0002 formula or score.",
        )
    compared_versions = False
    for field in PROJECT_LEVEL_FIELDS:
        groups = [(item, active(item, field)) for item in inputs]
        groups = [(item, rows) for item, rows in groups if rows]
        if len(groups) < 2:
            continue
        if len({item.report.document_version_id for item, _ in groups}) > 1:
            compared_versions = True
        signatures = [
            {
                json.dumps([observation.normalized_value, observation.unit])
                for observation, _ in rows
            }
            for _, rows in groups
        ]
        if all(signature == signatures[0] for signature in signatures):
            continue
        sources = {item.source_document_id for item, _ in groups}
        versions = {item.report.document_version_id for item, _ in groups}
        code = (
            "cross_document_difference"
            if len(sources) > 1
            else "cross_version_difference"
            if len(versions) > 1
            else "extractor_difference"
        )
        add(
            code,
            (field,),
            [link for _, rows in groups for _, link in rows],
            "Candidate values/units differ; newer retrieval time is not authority.",
        )
    return ProjectConsistencyReport(
        pipeline_run_id=pipeline_run_id,
        project_id=project_id,
        registry=registry,
        inputs=inputs,
        issues=tuple(issues),
        cross_document_comparison="performed" if compared_versions else "not_possible",
    )
