"""Strict experiment configuration; no credentials are accepted in JSON."""

from dataclasses import asdict, dataclass, field
import json
import math
from pathlib import Path


@dataclass
class Config:
    provider: str = "mock"
    model: str = "scripted-mock-v1"
    defenses: list[str] = field(default_factory=lambda: ["baseline", "boundary"])
    repetitions: int = 1
    max_output_tokens: int = 1024
    timeout_seconds: float = 60
    input_usd_per_million: float | None = None
    output_usd_per_million: float | None = None
    cached_input_usd_per_million: float | None = None

    def validate(self) -> None:
        if self.provider not in ("mock", "openai"):
            raise ValueError("provider must be mock or openai")
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("model must be a nonempty model id")
        if self.provider == "mock" and self.model != "scripted-mock-v1":
            raise ValueError("mock provider requires model scripted-mock-v1")
        if self.provider == "openai" and self.model in (
            "scripted-mock-v1", "REPLACE_WITH_YOUR_MODEL_ID"
        ):
            raise ValueError("Set model to an API model id available to your account")
        if (not isinstance(self.defenses, list) or not self.defenses
                or any(item not in ("baseline", "boundary") for item in self.defenses)
                or len(set(self.defenses)) != len(self.defenses)):
            raise ValueError("defenses must be a unique, nonempty list of baseline/boundary")
        for key, minimum in (("repetitions", 1), ("max_output_tokens", 16)):
            value = getattr(self, key)
            if type(value) is not int or value < minimum:
                raise ValueError(f"{key} must be an integer >= {minimum}")
        if (type(self.timeout_seconds) not in (int, float)
                or not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0):
            raise ValueError("timeout_seconds must be a positive finite number")
        for key in ("input_usd_per_million", "output_usd_per_million",
                    "cached_input_usd_per_million"):
            value = getattr(self, key)
            if value is not None and (type(value) not in (int, float)
                                      or not math.isfinite(value) or value < 0):
                raise ValueError(f"{key} must be null or a nonnegative finite number")

    def to_dict(self) -> dict:
        return asdict(self)


def load_config(path: Path | None) -> Config:
    data = {} if path is None else json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) - set(Config.__dataclass_fields__):
        raise ValueError("Config must be an object containing only documented config fields")
    config = Config(**data)
    config.validate()
    return config
