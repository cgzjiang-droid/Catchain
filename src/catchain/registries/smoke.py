"""Read-only Registry endpoint probes with explicit failure classification."""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True, slots=True)
class SmokeResult:
    registry: str
    url: str
    status: str
    http_status: int | None
    content_type: str | None
    body_bytes: int
    error_code: str | None


def classify_smoke_response(
    *, registry: str, url: str, status_code: int, content_type: str, body: bytes
) -> SmokeResult:
    normalized_type = content_type.lower().split(";", 1)[0].strip()
    if status_code == 403:
        status, error = "blocked", "http_403"
    elif status_code == 404:
        status, error = "not_found", "http_404"
    elif status_code == 429:
        status, error = "rate_limited", "http_429"
    elif status_code >= 500:
        status, error = "transient_failure", f"http_{status_code}"
    elif status_code < 200 or status_code >= 300:
        status, error = "blocked", f"http_{status_code}"
    elif normalized_type == "application/json":
        try:
            json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            status, error = "endpoint_mismatch", "invalid_json"
        else:
            status, error = "ok", None
    elif normalized_type in {"text/html", "application/xhtml+xml"}:
        lowered = body.lower()
        if b"invalid page" in lowered or b"404 not found" in lowered:
            status, error = "not_found", "html_not_found"
        else:
            status, error = "endpoint_mismatch", "html_instead_of_data"
    else:
        status, error = "endpoint_mismatch", "unexpected_content_type"
    return SmokeResult(
        registry=registry,
        url=url,
        status=status,
        http_status=status_code,
        content_type=content_type,
        body_bytes=len(body),
        error_code=error,
    )


def smoke_test_url(*, registry: str, url: str, timeout_seconds: float = 20) -> SmokeResult:
    """Perform one bounded GET without writing to or mutating a Registry."""

    request = Request(url, headers={"User-Agent": "CATchain-registry-smoke/0.1"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            body = response.read(2_000_001)
            if len(body) > 2_000_000:
                return SmokeResult(
                    registry=registry,
                    url=url,
                    status="endpoint_mismatch",
                    http_status=response.status,
                    content_type=response.headers.get("Content-Type"),
                    body_bytes=len(body),
                    error_code="response_too_large",
                )
            return classify_smoke_response(
                registry=registry,
                url=url,
                status_code=response.status,
                content_type=response.headers.get("Content-Type", ""),
                body=body,
            )
    except HTTPError as error:
        return classify_smoke_response(
            registry=registry,
            url=url,
            status_code=error.code,
            content_type=error.headers.get("Content-Type", ""),
            body=error.read(2_000_001),
        )
    except (URLError, TimeoutError, OSError):
        return SmokeResult(
            registry=registry,
            url=url,
            status="transport_failure",
            http_status=None,
            content_type=None,
            body_bytes=0,
            error_code="network_error",
        )
