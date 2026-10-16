"""Offline scripted demonstration and a minimal OpenAI Responses API adapter."""

from dataclasses import dataclass
import json
import os
import re
import socket
from urllib import error, request

from sleeper_token.config import Config


class ProviderError(RuntimeError):
    """Public, credential-free provider failure."""


@dataclass
class Generation:
    text: str
    model: str
    status: str = "completed"
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_input_tokens: int | None = None
    response_id: str | None = None


class MockProvider:
    """Scripted outcomes for pipeline QA, NOT an LLM or a security benchmark."""

    def generate(self, instructions: str, user_input: str) -> Generation:
        document = json.loads(user_input)["retrieved_documents"][0]["content"]
        # Fixtures start with their factual paragraph. No answer key is passed here.
        text = document.split("\n\n", 1)[0]
        marker = re.search(r"\bST_CANARY_[A-Z0-9_]+\b", document)
        if marker and "untrusted evidence" not in instructions:
            text += " " + marker.group(0)
        return Generation(text=text, model="scripted-mock-v1")


class OpenAIProvider:
    def __init__(self, config: Config):
        self.config = config
        self.api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for provider=openai")

    def generate(self, instructions: str, user_input: str) -> Generation:
        payload = {
            "model": self.config.model,
            "instructions": instructions,
            "input": [{"role": "user", "content": user_input}],
            "max_output_tokens": self.config.max_output_tokens,
            "store": False,
        }
        req = request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}",
                     "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.config.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            # Do not copy server bodies or URLs into reports (may contain secrets).
            raise ProviderError(f"OpenAI HTTP {exc.code}; no automatic retry") from None
        except (error.URLError, TimeoutError, socket.timeout, OSError):
            raise ProviderError("OpenAI connection failed or timed out; no automatic retry") from None
        except (ValueError, UnicodeError):
            raise ProviderError("OpenAI returned invalid JSON") from None
        try:
            if not isinstance(data, dict):
                raise ValueError("Expected an object")
            for key in ("model", "id", "status"):
                if data.get(key) is not None and not isinstance(data[key], str):
                    raise ValueError(f"Invalid {key}")
            texts = [part["text"] for item in data.get("output", [])
                     if item.get("type") == "message"
                     for part in item.get("content", [])
                     if part.get("type") == "output_text"]
            usage = data.get("usage") or {}
            details = usage.get("input_tokens_details") or {}
            tokens = [usage.get("input_tokens"), usage.get("output_tokens"),
                      details.get("cached_tokens")]
            if any(value is not None and (type(value) is not int or value < 0)
                   for value in tokens):
                raise ValueError("Invalid token usage")
            if tokens[0] is not None and tokens[2] is not None and tokens[2] > tokens[0]:
                raise ValueError("Cached tokens exceed input tokens")
            return Generation(
                text="\n".join(texts), model=data.get("model") or self.config.model,
                status=data.get("status", "unknown"), input_tokens=tokens[0],
                output_tokens=tokens[1], cached_input_tokens=tokens[2],
                response_id=data.get("id"),
            )
        except (AttributeError, KeyError, TypeError, ValueError):
            raise ProviderError("OpenAI returned an unexpected response schema") from None


def make_provider(config: Config) -> MockProvider | OpenAIProvider:
    return MockProvider() if config.provider == "mock" else OpenAIProvider(config)
