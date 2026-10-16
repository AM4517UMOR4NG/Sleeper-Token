"""Offline behavior tests, including transport stubs; never call a paid API."""

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import asdict
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from sleeper_token.cli import main
from sleeper_token.config import Config, load_config
from sleeper_token.evaluation import contains_fact, evaluate, task_succeeds
from sleeper_token.providers import Generation, MockProvider, OpenAIProvider, ProviderError
from sleeper_token.reporting import markdown_report
from sleeper_token.runner import estimate_cost, run_experiment
from sleeper_token.scenarios import Scenario, load_scenarios


class ScenarioTests(unittest.TestCase):
    def test_builtin_suite_has_ten_valid_unique_pairs(self):
        scenarios = load_scenarios()
        self.assertEqual(len(scenarios), 10)
        self.assertEqual(len({s.id for s in scenarios}), 10)
        self.assertEqual({s.language for s in scenarios}, {"id", "id-en"})
        for scenario in scenarios:
            self.assertIn(scenario.clean_document, scenario.injected_document)
            self.assertTrue(task_succeeds(scenario.reference_answer, scenario))
            self.assertNotIn(scenario.attack_marker, scenario.clean_document)

    def test_invalid_fixtures_rejected(self):
        original = asdict(load_scenarios()[0])
        invalid = [
            {"id": "bad id"}, {"required_facts": []}, {"required_facts": ["wrong"]},
            {"forbidden_facts": [None]}, {"attack_marker": "missing"},
            {"reference_answer": "I don't know"}, {"unexpected": "field"},
            {"clean_document": original["attack_marker"]},
            {"injected_document": original["attack_marker"]},
        ]
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                Scenario.from_dict(original | changes)

    def test_duplicate_ids_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in ("a.json", "b.json"):
                (Path(directory) / name).write_text(json.dumps(asdict(load_scenarios()[0])), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                load_scenarios(Path(directory))

    def test_missing_and_empty_paths_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            for path in (Path(directory), Path(directory) / "missing"):
                with self.assertRaises(ValueError):
                    load_scenarios(path)


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.scenario = load_scenarios()[0]

    def test_task_and_attack_can_both_succeed(self):
        scores = evaluate(self.scenario.reference_answer + " " + self.scenario.attack_marker,
                          self.scenario, "injected")
        self.assertTrue(scores["task_success"])
        self.assertTrue(scores["attack_success"])

    def test_refusal_is_not_task_success(self):
        scores = evaluate("Saya tidak bisa membantu.", self.scenario, "injected")
        self.assertFalse(scores["task_success"])
        self.assertFalse(scores["attack_success"])

    def test_clean_has_no_attack_label(self):
        self.assertIsNone(evaluate(self.scenario.reference_answer, self.scenario, "clean")["attack_success"])

    def test_numeric_boundaries_case_and_unicode(self):
        self.assertFalse(contains_fact("112 hari kerja", "12 hari kerja"))
        self.assertTrue(contains_fact("１２ HARI\n KERJA", "12 hari kerja"))
        self.assertFalse(contains_fact("ST_CANARY_01_LEAVE_OTHER", self.scenario.attack_marker))

    def test_aliases_and_forbidden_facts(self):
        self.assertTrue(task_succeeds("Dua belas hari kerja setelah satu tahun.", self.scenario))
        self.assertFalse(task_succeeds(self.scenario.reference_answer + " 120 hari kerja.", self.scenario))


class ConfigTests(unittest.TestCase):
    def test_default_is_offline(self):
        self.assertEqual(load_config(None).provider, "mock")

    def test_invalid_values_fail_before_requests(self):
        changes = [
            {"provider": "other"}, {"repetitions": 0}, {"repetitions": True},
            {"max_output_tokens": 10}, {"timeout_seconds": float("nan")},
            {"input_usd_per_million": -1}, {"output_usd_per_million": True},
            {"defenses": []}, {"defenses": ["baseline", "baseline"]},
            {"defenses": ["unknown"]}, {"model": "another-mock"},
            {"provider": "openai", "model": "REPLACE_WITH_YOUR_MODEL_ID"},
        ]
        for values in changes:
            with self.subTest(values=values), self.assertRaises(ValueError):
                Config(**values).validate()

    def test_secret_or_unknown_fields_are_not_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text('{"api_key": "do-not-store"}', encoding="utf-8")
            with self.assertRaises(ValueError):
                load_config(path)


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.config = Config(provider="openai", model="test-model")

    def respond(self, data):
        context = unittest.mock.MagicMock()
        context.__enter__.return_value.read.return_value = json.dumps(data).encode("utf-8")
        return context

    def test_missing_key_fails_without_network(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}), self.assertRaises(ValueError):
            OpenAIProvider(self.config)

    def test_request_and_multiple_output_parts(self):
        data = {
            "id": "resp_test", "status": "completed", "model": "test-model-snapshot",
            "output": [
                {"type": "reasoning", "summary": []},
                {"type": "message", "content": [{"type": "output_text", "text": "First"},
                                                {"type": "output_text", "text": "Second"}]},
            ],
            "usage": {"input_tokens": 100, "output_tokens": 20,
                      "input_tokens_details": {"cached_tokens": 50}},
        }
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-secret"}), patch(
            "sleeper_token.providers.request.urlopen", return_value=self.respond(data)
        ) as send:
            output = OpenAIProvider(self.config).generate("system", "user")
        self.assertEqual(output.text, "First\nSecond")
        self.assertEqual(output.cached_input_tokens, 50)
        self.assertEqual(output.model, "test-model-snapshot")
        req = send.call_args.args[0]
        payload = json.loads(req.data)
        self.assertFalse(payload["store"])
        self.assertEqual(payload["input"], [{"role": "user", "content": "user"}])
        self.assertNotIn("test-secret", json.dumps(payload))
        self.assertEqual(req.full_url, "https://api.openai.com/v1/responses")

    def test_http_network_and_malformed_errors_are_sanitized(self):
        problems = [
            HTTPError("https://example.invalid/SECRET", 429, "SECRET", {}, io.BytesIO(b"SECRET")),
            URLError("SECRET"), TimeoutError("SECRET"),
        ]
        for problem in problems:
            with self.subTest(problem=type(problem).__name__), patch.dict(
                os.environ, {"OPENAI_API_KEY": "SECRET"}
            ), patch("sleeper_token.providers.request.urlopen", side_effect=problem) as send:
                with self.assertRaises(ProviderError) as caught:
                    OpenAIProvider(self.config).generate("system", "user")
                self.assertNotIn("SECRET", str(caught.exception))
                self.assertEqual(send.call_count, 1)
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test"}), patch(
            "sleeper_token.providers.request.urlopen", return_value=self.respond({"output": None})
        ), self.assertRaises(ProviderError):
            OpenAIProvider(self.config).generate("system", "user")

    def test_invalid_model_and_usage_schema_rejected(self):
        for data in ({"model": 17}, {"usage": {"input_tokens": True}},
                     {"usage": {"input_tokens": 10, "input_tokens_details": {"cached_tokens": 20}}}):
            with self.subTest(data=data), patch.dict(os.environ, {"OPENAI_API_KEY": "test"}), patch(
                "sleeper_token.providers.request.urlopen", return_value=self.respond(data)
            ), self.assertRaises(ProviderError):
                OpenAIProvider(self.config).generate("system", "user")


class RunnerTests(unittest.TestCase):
    def test_offline_comparison_is_explicitly_scripted(self):
        result = run_experiment(Config(repetitions=2), load_scenarios(), MockProvider())
        self.assertEqual(len(result["records"]), 80)
        self.assertTrue(result["simulation"])
        baseline, boundary = result["summary"]
        self.assertEqual(baseline["attack_success_rate"], 1)
        self.assertEqual(boundary["attack_success_rate"], 0)
        self.assertEqual(baseline["clean_task_success_rate"], 1)
        self.assertEqual(boundary["injected_task_success_rate"], 1)
        self.assertIn("SIMULATION ONLY", markdown_report(result))

    def test_errors_are_not_scored_as_blocked_attacks(self):
        provider = unittest.mock.Mock()
        provider.generate.side_effect = ProviderError("Failed")
        result = run_experiment(Config(), load_scenarios()[:1], provider)
        for summary in result["summary"]:
            self.assertEqual(summary["errors"], 2)
            self.assertEqual(summary["completed"], 0)
            self.assertIsNone(summary["attack_success_rate"])
        self.assertEqual(provider.generate.call_count, 4)

    def test_incomplete_retains_usage_but_not_score(self):
        provider = unittest.mock.Mock()
        provider.generate.return_value = Generation("partial", "snapshot", "incomplete", 30, 10)
        result = run_experiment(Config(), load_scenarios()[:1], provider)
        row = result["records"][0]
        self.assertEqual(row["status"], "error")
        self.assertEqual(row["input_tokens"], 30)
        self.assertIsNone(row["task_success"])

    def test_empty_completed_response_is_not_scored(self):
        provider = unittest.mock.Mock()
        provider.generate.return_value = Generation("  ", "test")
        result = run_experiment(Config(), load_scenarios()[:1], provider)
        self.assertTrue(all(row["status"] == "error" for row in result["records"]))

    def test_conditional_asr_requires_paired_clean_task_success(self):
        provider = unittest.mock.Mock()
        scenario = load_scenarios()[0]
        provider.generate.side_effect = [Generation("I don't know", "test"),
                                         Generation(scenario.attack_marker, "test")]
        result = run_experiment(Config(defenses=["baseline"]), [scenario], provider)
        summary = result["summary"][0]
        self.assertEqual(summary["attack_success_rate"], 1)
        self.assertEqual(summary["conditional_injected_scored"], 0)
        self.assertIsNone(summary["conditional_attack_success_rate"])

    def test_prompt_contains_no_answer_key_or_scoring_metadata(self):
        result = run_experiment(Config(), load_scenarios()[:1], MockProvider())
        prompt = json.loads(result["records"][0]["user_input"])
        self.assertEqual(set(prompt), {"question", "retrieved_documents"})
        self.assertNotIn("reference_answer", prompt)

    def test_cost_unknown_and_cache_aware(self):
        generation = Generation("ok", "test", input_tokens=100, output_tokens=20,
                                cached_input_tokens=50)
        config = Config(provider="openai", model="test", input_usd_per_million=2,
                        output_usd_per_million=5, cached_input_usd_per_million=1)
        self.assertAlmostEqual(estimate_cost(generation, config), .00025)
        config.cached_input_usd_per_million = None
        self.assertAlmostEqual(estimate_cost(generation, config), .0003)
        config.input_usd_per_million = None
        self.assertIsNone(estimate_cost(generation, config))


class CliTests(unittest.TestCase):
    def invoke(self, args):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return main(args)

    def test_cli_creates_complete_reports_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            args = ["run", "--output", str(output), "--scenario", "01_leave"]
            self.assertEqual(self.invoke(args), 0)
            records = (output / "calls.jsonl").read_text(encoding="utf-8").splitlines()
            result = json.loads((output / "results.json").read_text(encoding="utf-8"))
            self.assertEqual([json.loads(line) for line in records], result["records"])
            self.assertEqual(len(records), 4)
            self.assertTrue((output / "report.md").exists())
            self.assertEqual(self.invoke(args), 2)
            self.assertEqual((output / "calls.jsonl").read_text(encoding="utf-8").splitlines(), records)

    def test_unknown_scenario_and_invalid_repetitions(self):
        self.assertEqual(self.invoke(["run", "--scenario", "missing"]), 2)
        self.assertEqual(self.invoke(["run", "--repetitions", "0"]), 2)

    def test_failed_calls_preserve_report_and_signal_exit_one(self):
        provider = unittest.mock.Mock()
        provider.generate.side_effect = ProviderError("HTTP failure")
        with tempfile.TemporaryDirectory() as directory, patch(
            "sleeper_token.cli.make_provider", return_value=provider
        ):
            output = Path(directory) / "failed-run"
            self.assertEqual(self.invoke(["run", "--scenario", "01_leave", "--output", str(output)]), 1)
            result = json.loads((output / "results.json").read_text(encoding="utf-8"))
            self.assertEqual(sum(row["errors"] for row in result["summary"]), 4)
            self.assertTrue((output / "report.md").exists())

    def test_list_and_validate(self):
        self.assertEqual(self.invoke(["list"]), 0)
        self.assertEqual(self.invoke(["validate"]), 0)


if __name__ == "__main__":
    unittest.main()
