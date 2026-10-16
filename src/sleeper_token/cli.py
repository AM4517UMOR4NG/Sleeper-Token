"""Command-line interface. Offline mock mode is the default."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import uuid

from sleeper_token import __version__
from sleeper_token.config import load_config
from sleeper_token.providers import make_provider
from sleeper_token.runner import run_experiment, write_results
from sleeper_token.scenarios import load_scenarios


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Paired IPI evaluations for synthetic RAG fixtures")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("list", "validate", "run"):
        command = commands.add_parser(name)
        command.add_argument("--scenarios", type=Path, help="Custom JSON file or directory")
        if name == "run":
            command.add_argument("--config", type=Path, help="JSON experiment config; default is offline mock")
            command.add_argument("--output", type=Path, help="New output directory; never overwrites an existing directory")
            command.add_argument("--repetitions", type=int)
            command.add_argument("--scenario", action="append", help="Select an id (repeat to select multiple)")
    args = parser.parse_args(argv)
    try:
        scenarios = load_scenarios(args.scenarios)
        if args.command == "list":
            for scenario in scenarios:
                print(f"{scenario.id:24} {scenario.language:5} {scenario.family}")
            return 0
        if args.command == "validate":
            print(f"Validated {len(scenarios)} paired scenarios.")
            return 0
        config = load_config(args.config)
        if args.repetitions is not None:
            config.repetitions = args.repetitions
            config.validate()
        if args.scenario:
            missing = set(args.scenario) - {scenario.id for scenario in scenarios}
            if missing:
                raise ValueError("Unknown scenario ids: " + ", ".join(sorted(missing)))
            scenarios = [scenario for scenario in scenarios if scenario.id in args.scenario]
        provider = make_provider(config)
        output = args.output or Path("reports") / (
            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
        )
        output.mkdir(parents=True, exist_ok=False)
        total = len(scenarios) * 2 * len(config.defenses) * config.repetitions
        mode = "SIMULATION ONLY" if config.provider == "mock" else "LIVE API"
        print(f"{mode}: {total} calls, provider={config.provider}, model={config.model}", flush=True)
        with (output / "calls.jsonl").open("x", encoding="utf-8") as log:
            def record_call(record: dict) -> None:
                log.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
                log.flush()
                print(f"{record['scenario_id']} {record['defense']}/{record['variant']}: "
                      f"{record['status']}", flush=True)

            result = run_experiment(config, scenarios, provider, on_record=record_call)
        write_results(result, output)
        failures = sum(row["status"] == "error" for row in result["records"])
        print(f"Report: {(output / 'report.md').resolve()}")
        print(f"Completed: {total - failures}/{total}; errors: {failures}")
        return 1 if failures else 0
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Interrupted. Completed calls remain in the output directory's calls.jsonl.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
