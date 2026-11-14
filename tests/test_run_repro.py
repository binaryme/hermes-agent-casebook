import contextlib
import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from harness import run_repro

DIGEST_ONE = "sha256:" + "1" * 64
DIGEST_TWO = "sha256:" + "2" * 64
FIXED_MOMENT = datetime(2026, 11, 13, 12, 30, 5, tzinfo=timezone.utc)

IMAGES = {
    "image": "example/hermes",
    "tags": {
        "v1": {"digest": DIGEST_ONE, "published": "2026-01-01"},
        "v2": {"digest": DIGEST_TWO, "published": "2026-02-01"},
    },
}

PRINT_ALPHA = "echo OBSERVED=alpha\n"


def execution(returncode=0, stdout="", stderr="", timed_out=False, duration_s=1.5):
    return run_repro.Execution(returncode, stdout, stderr, timed_out, duration_s)


class FindObservedLinesTests(unittest.TestCase):
    def test_no_lines(self):
        self.assertEqual(run_repro.find_observed_lines("hello\nworld\n"), [])

    def test_single_line_among_noise(self):
        self.assertEqual(run_repro.find_observed_lines("noise\nOBSERVED=alpha\nmore\n"), ["alpha"])

    def test_prefix_must_start_the_line(self):
        self.assertEqual(run_repro.find_observed_lines("x OBSERVED=alpha\n"), [])

    def test_strips_carriage_return(self):
        self.assertEqual(run_repro.find_observed_lines("OBSERVED=alpha\r\n"), ["alpha"])

    def test_multiple_lines_are_all_returned(self):
        self.assertEqual(
            run_repro.find_observed_lines("OBSERVED=a\nOBSERVED=b\n"),
            ["a", "b"],
        )


class EvaluateTests(unittest.TestCase):
    def test_match(self):
        verdict = run_repro.evaluate(execution(stdout="OBSERVED=alpha\n"), "alpha")
        self.assertEqual((verdict.token, verdict.outcome), ("alpha", "match"))

    def test_behavior_changed(self):
        verdict = run_repro.evaluate(execution(stdout="OBSERVED=beta\n"), "alpha")
        self.assertEqual((verdict.token, verdict.outcome), ("beta", "behavior-changed"))

    def test_nonzero_exit_is_repro_error_even_with_a_line(self):
        verdict = run_repro.evaluate(execution(returncode=3, stdout="OBSERVED=alpha\n"), "alpha")
        self.assertEqual((verdict.token, verdict.outcome), (None, "repro-error"))

    def test_timeout_is_repro_error(self):
        verdict = run_repro.evaluate(
            execution(returncode=None, stdout="OBSERVED=alpha\n", timed_out=True),
            "alpha",
        )
        self.assertEqual((verdict.token, verdict.outcome), (None, "repro-error"))

    def test_missing_line_is_repro_error(self):
        verdict = run_repro.evaluate(execution(stdout="nothing here\n"), "alpha")
        self.assertEqual(verdict.outcome, "repro-error")
        self.assertIn("found 0", verdict.reason)

    def test_two_lines_are_repro_error(self):
        verdict = run_repro.evaluate(execution(stdout="OBSERVED=alpha\nOBSERVED=alpha\n"), "alpha")
        self.assertEqual(verdict.outcome, "repro-error")
        self.assertIn("found 2", verdict.reason)

    def test_empty_token_is_repro_error(self):
        verdict = run_repro.evaluate(execution(stdout="OBSERVED=\n"), "alpha")
        self.assertEqual(verdict.outcome, "repro-error")

    def test_token_with_space_is_repro_error(self):
        verdict = run_repro.evaluate(execution(stdout="OBSERVED=a b\n"), "alpha")
        self.assertEqual(verdict.outcome, "repro-error")

    def test_numeric_tokens_compare_as_text(self):
        verdict = run_repro.evaluate(execution(stdout="OBSERVED=401\n"), "401")
        self.assertEqual(verdict.outcome, "match")


class ImageAndExpectationTests(unittest.TestCase):
    def test_image_reference_uses_digest_only(self):
        reference, digest = run_repro.image_reference(IMAGES, "v1")
        self.assertEqual(reference, f"example/hermes@{DIGEST_ONE}")
        self.assertEqual(digest, DIGEST_ONE)

    def test_unpinned_tag_is_rejected(self):
        with self.assertRaises(run_repro.ConfigError):
            run_repro.image_reference(IMAGES, "v9")

    def test_expected_token_lookup(self):
        self.assertEqual(run_repro.expected_token({"v1": "alpha"}, "v1"), "alpha")

    def test_missing_expectation_is_rejected(self):
        with self.assertRaises(run_repro.ConfigError):
            run_repro.expected_token({"v1": "alpha"}, "v2")

    def test_override_wins_and_allows_missing_expectation(self):
        self.assertEqual(run_repro.expected_token({}, "v2", override="beta"), "beta")

    def test_slug_and_tag_validation(self):
        self.assertEqual(run_repro.validate_slug("webhook-first-skill-only"), "webhook-first-skill-only")
        self.assertEqual(run_repro.validate_tag("v2026.8.13"), "v2026.8.13")
        for bad in ("../x", "A b", "", "a/b"):
            with self.assertRaises(run_repro.ConfigError):
                run_repro.validate_slug(bad)
        for bad in ("../x", "v1/../v2", "", "-v1"):
            with self.assertRaises(run_repro.ConfigError):
                run_repro.validate_tag(bad)


class EnvironmentTests(unittest.TestCase):
    def test_exports_every_contract_variable_and_keeps_the_rest(self):
        env = run_repro.build_environment(
            {"PATH": "/usr/bin", "KEEP": "1"},
            "example/hermes@sha256:abc",
            "v1",
            Path("/repo/harness"),
            Path("/repo/entries/demo"),
            Path("/tmp/work"),
        )
        self.assertEqual(env["HERMES_IMAGE"], "example/hermes@sha256:abc")
        self.assertEqual(env["HARNESS"], "/repo/harness")
        self.assertEqual(env["ENTRY_DIR"], "/repo/entries/demo")
        self.assertEqual(env["FIXTURES"], "/repo/entries/demo/fixtures")
        self.assertEqual(env["WORK"], "/tmp/work")
        self.assertEqual(env["HERMES_TAG"], "v1")
        self.assertEqual(env["KEEP"], "1")

    def test_does_not_mutate_the_base_environment(self):
        base = {"PATH": "/usr/bin"}
        run_repro.build_environment(base, "i@d", "v1", Path("/h"), Path("/e"), Path("/w"))
        self.assertEqual(base, {"PATH": "/usr/bin"})


class DescriptionTests(unittest.TestCase):
    def test_runner_prefers_github_variables(self):
        self.assertEqual(
            run_repro.describe_runner({"RUNNER_OS": "Linux", "RUNNER_ARCH": "X64"}, "Darwin", "arm64"),
            "Linux-X64",
        )

    def test_runner_falls_back_to_platform(self):
        self.assertEqual(run_repro.describe_runner({}, "Darwin", "arm64"), "Darwin-arm64")

    def test_run_url_needs_all_three_variables(self):
        env = {
            "GITHUB_SERVER_URL": "https://github.com",
            "GITHUB_REPOSITORY": "binaryme/hermes-agent-casebook",
            "GITHUB_RUN_ID": "42",
        }
        self.assertEqual(
            run_repro.describe_run_url(env),
            "https://github.com/binaryme/hermes-agent-casebook/actions/runs/42",
        )
        del env["GITHUB_RUN_ID"]
        self.assertIsNone(run_repro.describe_run_url(env))

    def test_timestamp_is_utc_with_z_suffix(self):
        self.assertEqual(run_repro.format_timestamp(FIXED_MOMENT), "2026-11-13T12:30:05Z")

    def test_result_path(self):
        self.assertEqual(
            run_repro.result_path("results", "demo", "v1"),
            Path("results/demo/v1.json"),
        )


class BuildResultTests(unittest.TestCase):
    def test_keys_are_exactly_the_contract_keys(self):
        verdict = run_repro.Verdict("alpha", "match", None)
        result = run_repro.build_result(
            "demo", "v1", DIGEST_ONE, verdict, "alpha", execution(duration_s=1.23456),
            "Linux-X64", FIXED_MOMENT, None,
        )
        self.assertEqual(
            list(result),
            ["slug", "tag", "digest", "token", "expected", "class", "duration_s", "runner", "timestamp_utc", "run_url"],
        )
        self.assertEqual(result["duration_s"], 1.235)
        self.assertEqual(result["class"], "match")
        self.assertIsNone(result["run_url"])


class FakeRepoCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repo"
        self.results = Path(self.temp.name) / "results"
        (self.root / "harness").mkdir(parents=True)
        (self.root / "harness" / "images.json").write_text(json.dumps(IMAGES), encoding="utf-8")
        self.env = {"PATH": os.environ["PATH"]}

    def add_entry(self, slug, body, expect):
        entry = self.root / "entries" / slug
        entry.mkdir(parents=True)
        (entry / "repro.sh").write_text(
            "#!/usr/bin/env bash\nset -euo pipefail\n" + body, encoding="utf-8"
        )
        (entry / "expect.json").write_text(json.dumps(expect), encoding="utf-8")
        return entry

    def run_entry(self, slug, tag, **options):
        options.setdefault("env", self.env)
        options.setdefault("clock", lambda: FIXED_MOMENT)
        return run_repro.run_entry(
            slug, tag, root=self.root, results_dir=self.results, **options
        )

    def read_result(self, slug, tag):
        return json.loads((self.results / slug / f"{tag}.json").read_text(encoding="utf-8"))


class RunEntryTests(FakeRepoCase):
    def test_match_writes_the_result_file(self):
        self.add_entry("demo", PRINT_ALPHA, {"v1": "alpha"})
        result, verdict, _ = self.run_entry("demo", "v1")
        self.assertEqual(verdict.outcome, "match")
        self.assertEqual(self.read_result("demo", "v1"), result)
        self.assertEqual(result["slug"], "demo")
        self.assertEqual(result["tag"], "v1")
        self.assertEqual(result["digest"], DIGEST_ONE)
        self.assertEqual(result["token"], "alpha")
        self.assertEqual(result["expected"], "alpha")
        self.assertEqual(result["timestamp_utc"], "2026-11-13T12:30:05Z")

    def test_behavior_changed(self):
        self.add_entry("demo", "echo OBSERVED=beta\n", {"v1": "alpha"})
        result, _, _ = self.run_entry("demo", "v1")
        self.assertEqual(result["class"], "behavior-changed")
        self.assertEqual(result["token"], "beta")
        self.assertEqual(result["expected"], "alpha")

    def test_nonzero_exit_is_repro_error(self):
        self.add_entry("demo", "echo OBSERVED=alpha\nexit 7\n", {"v1": "alpha"})
        result, verdict, _ = self.run_entry("demo", "v1")
        self.assertEqual(result["class"], "repro-error")
        self.assertIsNone(result["token"])
        self.assertIn("7", verdict.reason)

    def test_missing_observed_line_is_repro_error(self):
        self.add_entry("demo", "echo nothing\n", {"v1": "alpha"})
        result, _, _ = self.run_entry("demo", "v1")
        self.assertEqual(result["class"], "repro-error")

    def test_two_observed_lines_are_repro_error(self):
        self.add_entry("demo", "echo OBSERVED=alpha\necho OBSERVED=alpha\n", {"v1": "alpha"})
        result, _, _ = self.run_entry("demo", "v1")
        self.assertEqual(result["class"], "repro-error")

    def test_timeout_is_repro_error_and_returns_quickly(self):
        self.add_entry("demo", "sleep 30\necho OBSERVED=alpha\n", {"v1": "alpha"})
        result, verdict, execution = self.run_entry("demo", "v1", timeout=1)
        self.assertEqual(result["class"], "repro-error")
        self.assertTrue(execution.timed_out)
        self.assertLess(execution.duration_s, 15)
        self.assertIn("timed out", verdict.reason)

    def test_repro_sees_the_contract_environment(self):
        body = (
            'printf "%s\\n" "$HERMES_IMAGE" "$HARNESS" "$ENTRY_DIR" "$FIXTURES" "$WORK" "$HERMES_TAG"'
            ' > "$ENTRY_DIR/seen.txt"\n'
            'test -d "$WORK"\n'
            "echo OBSERVED=alpha\n"
        )
        entry = self.add_entry("demo", body, {"v2": "alpha"})
        self.run_entry("demo", "v2")
        image, harness, entry_dir, fixtures, work, tag = (
            (entry / "seen.txt").read_text(encoding="utf-8").splitlines()
        )
        self.assertEqual(image, f"example/hermes@{DIGEST_TWO}")
        self.assertEqual(harness, str(self.root / "harness"))
        self.assertEqual(entry_dir, str(entry))
        self.assertEqual(fixtures, str(entry / "fixtures"))
        self.assertEqual(tag, "v2")
        self.assertFalse(Path(work).exists())

    def test_work_directory_is_fresh_for_each_run(self):
        body = (
            'echo "$WORK" >> "$ENTRY_DIR/works.txt"\n'
            'test -z "$(ls -A "$WORK")"\n'
            'touch "$WORK/leftover"\n'
            "echo OBSERVED=alpha\n"
        )
        entry = self.add_entry("demo", body, {"v1": "alpha"})
        first, _, _ = self.run_entry("demo", "v1")
        second, _, _ = self.run_entry("demo", "v1")
        self.assertEqual(first["class"], "match")
        self.assertEqual(second["class"], "match")
        works = (entry / "works.txt").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(set(works)), 2)

    def test_repro_runs_inside_the_work_directory(self):
        body = 'test "$(pwd -P)" = "$(cd "$WORK" && pwd -P)"\necho OBSERVED=alpha\n'
        self.add_entry("demo", body, {"v1": "alpha"})
        result, _, _ = self.run_entry("demo", "v1")
        self.assertEqual(result["class"], "match")

    def test_run_url_and_runner_come_from_the_environment(self):
        self.add_entry("demo", PRINT_ALPHA, {"v1": "alpha"})
        env = dict(
            self.env,
            RUNNER_OS="Linux",
            RUNNER_ARCH="X64",
            GITHUB_SERVER_URL="https://github.com",
            GITHUB_REPOSITORY="binaryme/hermes-agent-casebook",
            GITHUB_RUN_ID="99",
        )
        result, _, _ = self.run_entry("demo", "v1", env=env)
        self.assertEqual(result["runner"], "Linux-X64")
        self.assertEqual(
            result["run_url"],
            "https://github.com/binaryme/hermes-agent-casebook/actions/runs/99",
        )

    def test_unpinned_tag_raises_and_writes_nothing(self):
        self.add_entry("demo", PRINT_ALPHA, {"v9": "alpha"})
        with self.assertRaises(run_repro.ConfigError):
            self.run_entry("demo", "v9")
        self.assertFalse(self.results.exists())

    def test_tag_without_expectation_raises(self):
        self.add_entry("demo", PRINT_ALPHA, {"v1": "alpha"})
        with self.assertRaises(run_repro.ConfigError):
            self.run_entry("demo", "v2")

    def test_expect_override_allows_a_tag_without_expectation(self):
        self.add_entry("demo", PRINT_ALPHA, {"v1": "alpha"})
        result, _, _ = self.run_entry("demo", "v2", expect_override="alpha")
        self.assertEqual(result["class"], "match")
        result, _, _ = self.run_entry("demo", "v2", expect_override="beta")
        self.assertEqual(result["class"], "behavior-changed")

    def test_images_path_override_supplies_an_unpinned_tag(self):
        self.add_entry("demo", PRINT_ALPHA, {"v1": "alpha"})
        extended = json.loads(json.dumps(IMAGES))
        extended["tags"]["v3"] = {"digest": "sha256:" + "3" * 64, "published": "2026-03-01"}
        images_path = Path(self.temp.name) / "images.json"
        images_path.write_text(json.dumps(extended), encoding="utf-8")
        result, _, _ = self.run_entry("demo", "v3", images_path=images_path, expect_override="alpha")
        self.assertEqual(result["digest"], "sha256:" + "3" * 64)
        self.assertEqual(result["class"], "match")

    def test_missing_entry_raises(self):
        with self.assertRaises(run_repro.ConfigError):
            self.run_entry("ghost", "v1")

    def test_invalid_slug_is_rejected_before_touching_the_filesystem(self):
        with self.assertRaises(run_repro.ConfigError):
            self.run_entry("../escape", "v1")

    def test_injected_runner_receives_script_env_cwd_and_timeout(self):
        entry = self.add_entry("demo", PRINT_ALPHA, {"v1": "alpha"})
        calls = []

        def fake_runner(script, env, cwd, timeout):
            calls.append((script, env, cwd, timeout))
            return execution(stdout="OBSERVED=alpha\n")

        result, _, _ = self.run_entry("demo", "v1", runner=fake_runner, timeout=17)
        script, env, cwd, timeout = calls[0]
        self.assertEqual(script, entry / "repro.sh")
        self.assertEqual(env["HERMES_TAG"], "v1")
        self.assertEqual(env["WORK"], str(cwd))
        self.assertEqual(timeout, 17)
        self.assertEqual(result["class"], "match")


class MainTests(FakeRepoCase):
    def call_main(self, *args):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = run_repro.main(
                [*args, "--results-dir", str(self.results)],
                root=self.root,
                env=self.env,
            )
        return code, stderr.getvalue()

    def test_exit_zero_only_on_match(self):
        self.add_entry("demo", PRINT_ALPHA, {"v1": "alpha", "v2": "beta"})
        code, _ = self.call_main("--entry", "demo", "--tag", "v1")
        self.assertEqual(code, 0)
        code, _ = self.call_main("--entry", "demo", "--tag", "v2")
        self.assertEqual(code, 1)
        self.assertEqual(self.read_result("demo", "v2")["class"], "behavior-changed")

    def test_repro_error_exits_one_and_reports_stderr(self):
        self.add_entry("demo", "echo boom >&2\nexit 4\n", {"v1": "alpha"})
        code, output = self.call_main("--entry", "demo", "--tag", "v1")
        self.assertEqual(code, 1)
        self.assertIn("repro-error", output)
        self.assertIn("boom", output)

    def test_configuration_problems_exit_two(self):
        self.add_entry("demo", PRINT_ALPHA, {"v1": "alpha"})
        code, output = self.call_main("--entry", "demo", "--tag", "v9")
        self.assertEqual(code, 2)
        self.assertIn("not pinned", output)

    def test_all_tags_runs_every_expected_tag(self):
        self.add_entry("demo", PRINT_ALPHA, {"v1": "alpha", "v2": "alpha"})
        code, _ = self.call_main("--entry", "demo", "--all-tags")
        self.assertEqual(code, 0)
        self.assertEqual(self.read_result("demo", "v1")["class"], "match")
        self.assertEqual(self.read_result("demo", "v2")["class"], "match")

    def test_all_tags_fails_when_any_tag_does_not_match(self):
        self.add_entry("demo", PRINT_ALPHA, {"v1": "alpha", "v2": "beta"})
        code, _ = self.call_main("--entry", "demo", "--all-tags")
        self.assertEqual(code, 1)
        self.assertEqual(self.read_result("demo", "v1")["class"], "match")
        self.assertEqual(self.read_result("demo", "v2")["class"], "behavior-changed")

    def test_expect_override_through_the_cli(self):
        self.add_entry("demo", PRINT_ALPHA, {"v1": "alpha"})
        code, _ = self.call_main("--entry", "demo", "--tag", "v2", "--expect", "alpha")
        self.assertEqual(code, 0)

    def test_expect_with_all_tags_is_rejected(self):
        self.add_entry("demo", PRINT_ALPHA, {"v1": "alpha"})
        code, _ = self.call_main("--entry", "demo", "--all-tags", "--expect", "alpha")
        self.assertEqual(code, 2)

    def test_tag_and_all_tags_are_exclusive(self):
        self.add_entry("demo", PRINT_ALPHA, {"v1": "alpha"})
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            run_repro.main(["--entry", "demo", "--tag", "v1", "--all-tags"], root=self.root)


if __name__ == "__main__":
    unittest.main()
