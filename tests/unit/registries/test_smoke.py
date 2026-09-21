from catchain.registries.smoke import classify_smoke_response


def test_smoke_classifies_html_shell_as_endpoint_mismatch() -> None:
    result = classify_smoke_response(
        registry="verra",
        url="https://registry.verra.org/uiapi/resource/resourceSummary/7",
        status_code=200,
        content_type="text/html",
        body=b"<!doctype html><html><head><base href='/'>",
    )

    assert result.status == "endpoint_mismatch"
    assert result.error_code == "html_instead_of_data"


def test_smoke_classifies_forbidden_without_calling_it_empty() -> None:
    result = classify_smoke_response(
        registry="gold_standard",
        url="https://assurance-platform.goldstandard.org/api/public/project-documents/7",
        status_code=403,
        content_type="text/html",
        body=b"<html><h1>403 Forbidden</h1></html>",
    )

    assert result.status == "blocked"
    assert result.error_code == "http_403"


def test_smoke_accepts_json_data_response() -> None:
    result = classify_smoke_response(
        registry="verra",
        url="https://example.test/resource/7",
        status_code=200,
        content_type="application/json",
        body=b'{"documentGroups": []}',
    )

    assert result.status == "ok"
    assert result.error_code is None
