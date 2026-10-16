"""Load and validate paired, synthetic retrieval fixtures."""

from dataclasses import dataclass
from importlib import resources
import json
from pathlib import Path
import re
from typing import Any


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    language: str
    family: str
    question: str
    clean_document: str
    injected_document: str
    reference_answer: str
    required_facts: list[list[str]]
    forbidden_facts: list[str]
    attack_marker: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Scenario":
        if not isinstance(data, dict):
            raise ValueError("Scenario must be a JSON object")
        if set(data) != set(cls.__dataclass_fields__):
            raise ValueError("Scenario fields must match the documented schema exactly")
        for key in set(cls.__dataclass_fields__) - {"required_facts", "forbidden_facts"}:
            if not isinstance(data[key], str) or not data[key].strip():
                raise ValueError(f"Scenario field {key} must be a nonempty string")
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", data["id"]):
            raise ValueError("Scenario id must use lowercase letters, digits, '_' or '-'")
        facts = data["required_facts"]
        if not isinstance(facts, list) or not facts:
            raise ValueError("required_facts must contain at least one alias group")
        if any(not isinstance(group, list) or not group or any(
            not isinstance(alias, str) or not alias.strip() for alias in group
        ) for group in facts):
            raise ValueError("Each required fact needs a nonempty list of string aliases")
        forbidden = data["forbidden_facts"]
        if not isinstance(forbidden, list) or any(
            not isinstance(term, str) or not term.strip() for term in forbidden
        ):
            raise ValueError("forbidden_facts must be a list of nonempty strings")
        marker = data["attack_marker"]
        if not re.fullmatch(r"ST_CANARY_[A-Z0-9_]+", marker):
            raise ValueError("attack_marker must have form ST_CANARY_<UPPERCASE_ID>")
        if marker.casefold() in data["clean_document"].casefold():
            raise ValueError("Clean document must not contain the attack marker")
        if marker not in data["injected_document"]:
            raise ValueError("Injected document must contain the attack marker")
        if data["clean_document"] not in data["injected_document"]:
            raise ValueError("Injected document must preserve the complete clean document")
        from sleeper_token.evaluation import contains_fact, task_succeeds

        if contains_fact(data["question"] + " " + data["reference_answer"], marker):
            raise ValueError("Question and reference answer must not contain the marker")
        scenario = cls(**data)
        if not task_succeeds(scenario.reference_answer, scenario):
            raise ValueError("Reference answer does not pass its own task checks")
        return scenario


def load_scenarios(path: Path | None = None) -> list[Scenario]:
    if path is None:
        root = resources.files("sleeper_token").joinpath("data")
        files = sorted((item for item in root.iterdir() if item.name.endswith(".json")),
                       key=lambda item: item.name)
    elif path.is_dir():
        files = sorted(path.glob("*.json"))
    elif path.is_file():
        files = [path]
    else:
        raise ValueError(f"Scenario path does not exist: {path}")
    if not files:
        raise ValueError("No JSON scenarios found")
    scenarios = []
    ids: set[str] = set()
    markers: set[str] = set()
    for file in files:
        try:
            scenario = Scenario.from_dict(json.loads(file.read_text(encoding="utf-8")))
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Invalid scenario {file.name}: {exc}") from exc
        if scenario.id in ids or scenario.attack_marker in markers:
            raise ValueError(f"Duplicate scenario id or attack marker: {scenario.id}")
        ids.add(scenario.id)
        markers.add(scenario.attack_marker)
        scenarios.append(scenario)
    return scenarios
