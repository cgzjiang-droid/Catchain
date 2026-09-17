import io
import json
import urllib.error
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from catchain.domain import ParsedDocument, ParsedPage, Registry
from catchain.extraction.llm.providers import DeepSeekProvider, ProviderError, read_deepseek_key
from catchain.extraction.llm.workflow import CostRates, extract_one_call
from catchain.parsing.quality import measure_text_quality


class FixtureHttpResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def api_body(content, finish="stop"):
    return {
        "id": "fixture-1",
        "model": "deepseek-flash",
        "choices": [{"message": {"content": content}, "finish_reason": finish}],
        "usage": {"prompt_tokens": 50, "completion_tokens": 30},
    }


def parsed():
    text = "Project title: Example Wind Project"
    return ParsedDocument(
        document_version_id=uuid4(),
        parser_name="fixture",
        parser_version="1",
        created_at=datetime.now(UTC),
        pages=(
            ParsedPage(
                page_number=1,
                text=text,
                char_start=0,
                char_end=len(text),
                quality=measure_text_quality(text),
            ),
        ),
    )


def candidate(quote="Project title: Example Wind Project"):
    return json.dumps(
        {
            "observations": [
                {
                    "field_name": "project_name",
                    "raw_value": "Example Wind Project",
                    "normalized_value": "Example Wind Project",
                    "unit": None,
                    "missing_reason": None,
                    "evidence": [{"page_number": 1, "quote": quote}],
                }
            ]
        }
    )


def invoke(tmp_path, monkeypatch, body, document=None):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request)
        assert timeout == 60
        payload = json.loads(request.data)
        assert payload["response_format"] == {"type": "json_object"}
        assert payload["thinking"] == {"type": "disabled"}
        assert payload["max_tokens"] == 1024
        return FixtureHttpResponse(json.dumps(body).encode())

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    artifact = extract_one_call(
        document or parsed(),
        provider=DeepSeekProvider(api_key="secret-test-key"),
        page_numbers=(1,),
        requested_fields=("project_name",),
        project_id="VCS1",
        registry=Registry.VERRA,
        output_dir=tmp_path,
    )
    return artifact, calls


def test_provider_and_workflow_preserve_response_usage_and_trusted_run(tmp_path, monkeypatch):
    artifact, calls = invoke(tmp_path, monkeypatch, api_body(candidate()))
    assert len(calls) == 1
    assert artifact.reused is False
    result = json.loads(artifact.path.read_text())
    assert result["run"]["status"] == "succeeded"
    assert result["result"]["pipeline_run_id"] == result["run"]["pipeline_run_id"]
    assert result["result"]["observations"][0]["validation_status"] == "unvalidated"
    response_path = tmp_path / "runs" / result["run"]["pipeline_run_id"] / "response.json"
    reply = json.loads(response_path.read_text())
    assert reply["input_tokens"] == 50 and reply["output_tokens"] == 30
    assert result["call_metrics"]["actual_estimated_cost_usd"] is None
    assert "secret-test-key" not in "".join(p.read_text() for p in tmp_path.rglob("*.json"))


@pytest.mark.parametrize(
    "body",
    [
        api_body(""),
        api_body(candidate(), "length"),
        api_body("{bad json"),
        api_body(candidate("invented quote")),
    ],
)
def test_failed_calls_keep_raw_response_and_failure_without_success(tmp_path, monkeypatch, body):
    with pytest.raises(ProviderError):
        invoke(tmp_path, monkeypatch, body)
    directory = next((tmp_path / "runs").iterdir())
    assert (directory / "response.json").exists()
    assert not (directory / "result.json").exists()
    failure = json.loads((directory / "failed.json").read_text())
    assert failure["run"]["status"] == "failed"
    assert "secret-test-key" not in (directory / "failed.json").read_text()


def test_auth_error_is_sanitized_and_not_retried(tmp_path, monkeypatch):
    calls = []

    def error(request, timeout):
        calls.append(request)
        raise urllib.error.HTTPError(request.full_url, 401, "secret-test-key", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", error)
    with pytest.raises(ProviderError, match="HTTP 401"):
        extract_one_call(
            parsed(),
            provider=DeepSeekProvider(api_key="secret-test-key"),
            page_numbers=(1,),
            requested_fields=("project_name",),
            project_id="VCS1",
            registry=Registry.VERRA,
            output_dir=tmp_path,
        )
    assert len(calls) == 1
    assert "secret-test-key" not in next(tmp_path.glob("runs/*/failed.json")).read_text()


def test_matching_completed_input_reuses_cache_without_a_second_api_call(tmp_path, monkeypatch):
    document = parsed()
    artifact, calls = invoke(tmp_path, monkeypatch, api_body(candidate()), document)
    cached, repeat_calls = invoke(tmp_path, monkeypatch, api_body(candidate()), document)
    assert artifact.path == cached.path
    assert cached.reused is True
    assert len(calls) == 1
    assert repeat_calls == []


def test_cost_ceiling_blocks_call_and_configured_rates_are_recorded(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("must not call provider")

    monkeypatch.setattr("urllib.request.urlopen", forbidden)
    with pytest.raises(ValueError, match="exceeds"):
        extract_one_call(
            parsed(),
            provider=DeepSeekProvider(api_key="test-key"),
            page_numbers=(1,),
            requested_fields=("project_name",),
            project_id="VCS1",
            registry=Registry.VERRA,
            output_dir=tmp_path,
            cost_rates=CostRates(Decimal("100"), Decimal("100")),
            max_estimated_cost_usd=Decimal("0"),
        )
    assert not list(tmp_path.iterdir())


def test_configured_rates_record_actual_usage_cost(tmp_path, monkeypatch):
    rates = CostRates(Decimal("100"), Decimal("100"))
    artifact, calls = invoke(tmp_path, monkeypatch, api_body(candidate()))
    assert len(calls) == 1
    result = json.loads(artifact.path.read_text())
    assert result["call_metrics"]["actual_estimated_cost_usd"] is None

    priced = extract_one_call(
        parsed(),
        provider=DeepSeekProvider(api_key="secret-test-key"),
        page_numbers=(1,),
        requested_fields=("project_name",),
        project_id="VCS1",
        registry=Registry.VERRA,
        output_dir=tmp_path / "priced",
        cost_rates=rates,
    )
    # The fixture network patch remains active: 50 input and 30 output tokens.
    priced_result = json.loads(priced.path.read_text())
    assert priced_result["call_metrics"]["actual_estimated_cost_usd"] == "0.008"


def test_env_wins_over_literal_config_and_empty_key_is_rejected(tmp_path, monkeypatch):
    config = tmp_path / ".env"
    config.write_text("DEEPSEEK_API_KEY=local-test-key\n")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    assert read_deepseek_key(config) == "local-test-key"
    monkeypatch.setenv("DEEPSEEK_API_KEY", "environment-test-key")
    assert read_deepseek_key(config) == "environment-test-key"
    monkeypatch.delenv("DEEPSEEK_API_KEY")
    config.write_text("DEEPSEEK_API_KEY=\n")
    with pytest.raises(ProviderError):
        read_deepseek_key(config)


def test_budget_or_unknown_field_failure_never_calls_provider(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("must not call provider")

    monkeypatch.setattr("urllib.request.urlopen", forbidden)
    for fields, budget in [(("made_up",), 1024), (("project_name",), 4097)]:
        with pytest.raises(ValueError):
            extract_one_call(
                parsed(),
                provider=DeepSeekProvider(api_key="test-key"),
                page_numbers=(1,),
                requested_fields=fields,
                project_id="VCS1",
                registry=Registry.VERRA,
                output_dir=tmp_path,
                max_output_tokens=budget,
            )
    assert not list(tmp_path.iterdir())
