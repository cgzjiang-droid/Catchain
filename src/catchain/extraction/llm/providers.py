"""Single-call DeepSeek JSON mode adapter; independent workflow checks the facts."""

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from pydantic import Field, StrictInt, StrictStr

from catchain.domain.common import ImmutableDomainModel


class ProviderError(RuntimeError):
    """Sanitized failure: never include request headers or API response error text."""


class ProviderReply(ImmutableDomainModel):
    response_id: StrictStr
    model: StrictStr
    content: StrictStr
    finish_reason: StrictStr
    input_tokens: StrictInt = Field(ge=0)
    output_tokens: StrictInt = Field(ge=0)
    latency_seconds: float = Field(ge=0)


def read_deepseek_key(config_file: Path = Path(".env")) -> str:
    """Environment wins; read one literal key without evaluating shell expressions."""
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key and config_file.is_file():
        for line in config_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("DEEPSEEK_API_KEY="):
                key = line.partition("=")[2].strip().strip('"').strip("'")
    if not key or any(character.isspace() for character in key):
        raise ProviderError("DEEPSEEK_API_KEY is missing or contains whitespace")
    return key


class DeepSeekProvider:
    name = "deepseek"

    def __init__(self, *, api_key: str, model: str = "deepseek-flash"):
        if not api_key.strip() or any(character.isspace() for character in api_key):
            raise ProviderError("invalid API key configuration")
        if model not in {"deepseek-flash", "deepseek-v4-pro"}:
            raise ProviderError("unsupported model; select an explicitly supported model")
        self._api_key = api_key
        self.model = model

    def extract(
        self, *, system_prompt: str, input_json: str, max_output_tokens: int
    ) -> ProviderReply:
        if not 1 <= max_output_tokens <= 4096:
            raise ProviderError("output token limit must be between 1 and 4096")
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": input_json},
            ],
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
            "max_tokens": max_output_tokens,
            "stream": False,
        }
        encoded = json.dumps(payload, ensure_ascii=False).encode()
        if len(encoded) > 64000:
            raise ProviderError("serialized request byte budget exceeded")
        request = urllib.request.Request(
            "https://api.deepseek.com/chat/completions",
            data=encoded,
            headers={
                "Authorization": "Bearer " + self._api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                # ponytail: buffered small responses; streaming only if output budgets grow.
                raw = response.read(1_000_001)
                if len(raw) > 1_000_000:
                    raise ProviderError("API response byte budget exceeded")
                body = json.loads(raw)
            choice = body["choices"][0]
            usage = body["usage"]
            return ProviderReply(
                response_id=body["id"],
                model=body["model"],
                content=choice["message"]["content"] or "",
                finish_reason=choice["finish_reason"],
                input_tokens=usage["prompt_tokens"],
                output_tokens=usage["completion_tokens"],
                latency_seconds=time.monotonic() - started,
            )
        except urllib.error.HTTPError as error:
            message = f"DeepSeek returned HTTP {error.code}; no automatic retry"
            raise ProviderError(message) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise ProviderError("DeepSeek connection failed; no automatic retry") from None
        except (ValueError, KeyError, TypeError, IndexError):
            raise ProviderError("DeepSeek response envelope/usage is invalid") from None
