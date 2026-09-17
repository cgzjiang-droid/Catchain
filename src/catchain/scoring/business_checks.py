"""Version/period gates and legacy algebra diagnostics, never quality scores."""

from decimal import Decimal, localcontext

from catchain.domain.assessment import AssessmentContext
from catchain.storage.document_repository import SqlAlchemyDocumentRepository

ER_FIELDS = ("be_value_tco2e", "pe_value_tco2e", "le_value_tco2e", "er_reported_tco2e")
PERIOD_DIMENSIONS = {
    "D05": ("electricity_generated_mwh", "electricity_exported_mwh"),
    "D06": ("pe_value_tco2e",),
    "D07": ("le_value_tco2e",),
    "D08": ER_FIELDS,
}


def check_business_inputs(
    readiness: dict, *, context: AssessmentContext | None, documents: SqlAlchemyDocumentRepository
) -> dict:
    facts = readiness["facts"]
    gates = []

    def block(code, fields=()):
        gates.append({"code": code, "fields": list(fields), "status": "blocked"})

    if facts.get("methodology_name", {}).get("value") != "ACM0002":
        block("methodology_scope_unconfirmed", ("methodology_name",))
    version = facts.get("methodology_version")
    if version is None or type(version["value"]) is not str or not version["value"].strip():
        block("methodology_version_missing", ("methodology_version",))
    if context is None:
        block("assessment_context_missing")
    else:
        if not context.authority_confirmed:
            block("authority_not_confirmed")
        for field, expected in (
            ("methodology_name", context.methodology_fact_id),
            ("methodology_version", context.methodology_version_fact_id),
        ):
            if facts.get(field, {}).get("fact_id") != str(expected):
                block("context_fact_identity_mismatch", (field,))
        for field, expected in context.period_fact_ids.items():
            if facts.get(field, {}).get("fact_id") != str(expected):
                block("context_fact_identity_mismatch", (field,))
        parsed = [documents.get_parsed(f["parsed_document_id"]) for f in facts.values()]
        for ref in context.evidence:
            pages = [
                p
                for doc in parsed
                if doc and str(doc.document_version_id) == str(ref.document_version_id)
                for p in doc.pages
                if p.page_number == ref.page_number
            ]
            if (
                ref.char_start is None
                or ref.char_end is None
                or not ref.quote.strip()
                or not any(
                    ref.char_end <= len(p.text)
                    and p.text[ref.char_start : ref.char_end] == ref.quote
                    for p in pages
                )
            ):
                block("context_evidence_not_grounded")
    dimensions = []
    period_ok = {}
    for dim in readiness["dimensions"]:
        fields = PERIOD_DIMENSIONS.get(dim["dimension_id"], ())
        missing_bindings = [
            f for f in fields if context is None or f not in context.period_fact_ids
        ]
        period_ok[dim["dimension_id"]] = not missing_bindings
        dimensions.append(
            {
                "dimension_id": dim["dimension_id"],
                "missing_fields": dim["missing_fields"],
                "period_binding_missing": missing_bindings,
                "deterministic_status": "blocked"
                if gates or dim["missing_fields"] or missing_bindings
                else "inputs_checked",
                "judgment_status": "business_rubric_pending",
                "score": None,
                "evidence_sufficiency": "not_assessed",
            }
        )
    diagnostic = {
        "formula": "BE - PE - LE",
        "policy": "legacy_er_identity_v1_not_methodology_compliance",
        "status": "blocked",
        "recalculated": None,
        "reported_minus_recalculated": None,
        "absolute_error_pct": None,
        "reason": "Required scoped inputs are not confirmed.",
    }
    if not gates and period_ok["D08"] and all(f in facts for f in ER_FIELDS):
        values = [facts[f]["value"] for f in ER_FIELDS]
        if all(
            type(v) in (int, float) and Decimal(str(v)).is_finite() and v >= 0 for v in values
        ) and all(facts[f]["unit"] == "tCO2e" for f in ER_FIELDS):
            with localcontext() as decimal_context:
                decimal_context.prec = 38
                be, pe, le, reported = map(lambda v: Decimal(str(v)), values)
                calculated = be - pe - le
                residual = reported - calculated
                diagnostic.update(
                    status="computed",
                    recalculated=str(calculated),
                    reported_minus_recalculated=str(residual),
                    absolute_error_pct=str(abs(residual / reported) * 100) if reported else None,
                    reason="Arithmetic diagnostic only; tolerance and compliance not determined."
                    if reported
                    else "Zero reported value: percentage is undefined.",
                )
        else:
            diagnostic["reason"] = (
                "Numeric values and tCO2e units are required; no automatic conversion."
            )
    return {
        "schema_version": "1.0.0",
        "policy_version": "business-gates-v1",
        "registry": readiness["registry"],
        "project_id": readiness["project_id"],
        "input_readiness_run_id": readiness.get("pipeline_run_id"),
        "facts": facts,
        "context": context.model_dump(mode="json") if context else None,
        "gates": gates,
        "dimensions": dimensions,
        "er_diagnostic": diagnostic,
        "total_score": None,
        "model_calls": 0,
        "limitations": [
            "human_attested_period_and_authority",
            "no_official_version_allowlist",
            "no_quality_rubric_or_tolerance",
            "no_automatic_evidence_sufficiency",
        ],
    }
