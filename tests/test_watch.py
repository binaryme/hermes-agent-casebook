import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from harness import run_repro, watch

DIGEST_OLD = "sha256:" + "a" * 64
DIGEST_NEW = "sha256:" + "c" * 64


def release_fetch(payload, status=200):
    def fetch(url, headers):
        return status, {}, json.dumps(payload).encode()
    return fetch


class LatestReleaseTests(unittest.TestCase):
    def test_returns_the_stable_tag(self):
        self.assertEqual(watch.latest_release(release_fetch({"tag_name": "v0.24.0"})), "v0.24.0")

    def test_skips_prereleases_drafts_and_canaries(self):
        for payload in (
            {"tag_name": "v0.24.0", "prerelease": True},
            {"tag_name": "v0.24.0", "draft": True},
            {"tag_name": "v0.24.0-canary.3"},
            {"tag_name": "v0.24.0-rc1"},
        ):
            self.assertIsNone(watch.latest_release(release_fetch(payload)), payload)

    def test_http_failure_is_an_error(self):
        with self.assertRaises(watch.WatchError):
            watch.latest_release(release_fetch({}, status=503))


class BaselineTests(unittest.TestCase):
    def test_newest_expectation_follows_the_pinned_order(self):
        self.assertEqual(
            watch.newest_expectation({"v1": "empty", "v2": "present"}, ["v1", "v2", "v3"]),
            ("v2", "present"),
        )

    def test_no_shared_tag(self):
        self.assertEqual(watch.newest_expectation({"x": "t"}, ["v1"]), (None, None))


class WatchCase(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "harness").mkdir()
        self.images = {"image": "example/hermes", "tags": {"v1.0.0": {"digest": DIGEST_OLD, "published": "2026-01-01"}}}
        (self.root / "harness" / "images.json").write_text(json.dumps(self.images))
        self.calls = []

    def add_entry(self, slug, expectations):
        entry = self.root / "entries" / slug
        entry.mkdir(parents=True)
        (entry / "expect.json").write_text(json.dumps(expectations))

    def resolver(self, image, tags, github_token=None):
        return {tag: {"digest": DIGEST_NEW, "published": "2026-12-01"} for tag in tags}

    def runner_with(self, tokens):
        def runner(slug, tag, root, images_path, results_dir, expect_override):
            pinned = json.loads(Path(images_path).read_text())
            self.calls.append((slug, tag, expect_override, pinned["tags"][tag]["digest"]))
            token = tokens[slug]
            outcome = run_repro.MATCH if token == expect_override else run_repro.BEHAVIOR_CHANGED
            return {"slug": slug, "token": token, "class": outcome}, None, None
        return runner


class WatchTests(WatchCase):
    def test_already_pinned_tag_does_nothing(self):
        self.assertIsNone(watch.watch(self.root, "v1.0.0", self.images, "results"))

    def test_no_entries_runs_nothing(self):
        outcome = watch.watch(self.root, "v2.0.0", self.images, "results", resolver=self.resolver)
        self.assertEqual(outcome["rows"], [])

    def test_runs_each_entry_against_the_new_digest_with_the_newest_expectation(self):
        self.add_entry("alpha", {"v1.0.0": "empty"})
        outcome = watch.watch(
            self.root, "v2.0.0", self.images, "results",
            runner=self.runner_with({"alpha": "present"}), resolver=self.resolver,
        )
        self.assertEqual(self.calls, [("alpha", "v2.0.0", "empty", DIGEST_NEW)])
        self.assertEqual(watch.changed_rows(outcome["rows"])[0]["token"], "present")

    def test_config_errors_become_repro_errors(self):
        self.add_entry("alpha", {"v1.0.0": "empty"})

        def failing_runner(*args, **kwargs):
            raise run_repro.ConfigError("missing repro")

        outcome = watch.watch(self.root, "v2.0.0", self.images, "results", runner=failing_runner, resolver=self.resolver)
        self.assertEqual(outcome["rows"][0]["class"], run_repro.REPRO_ERROR)


class PublishTests(unittest.TestCase):
    def fake_gh(self, existing):
        calls = []

        def run(command, **kwargs):
            calls.append(command)
            stdout = json.dumps(existing) if command[:3] == ["gh", "issue", "list"] else ""
            return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")
        return run, calls

    def test_creates_an_issue_when_none_is_open(self):
        run, calls = self.fake_gh([])
        self.assertEqual(watch.publish_report("Behavior change on v2", "body", run), ("created", None))
        self.assertEqual(calls[-1][:3], ["gh", "issue", "create"])

    def test_comments_on_the_open_issue_with_the_same_title(self):
        run, calls = self.fake_gh([
            {"number": 4, "title": "Behavior change on v2.1"},
            {"number": 7, "title": "Behavior change on v2"},
        ])
        self.assertEqual(watch.publish_report("Behavior change on v2", "body", run), ("commented", 7))
        self.assertEqual(calls[-1][:4], ["gh", "issue", "comment", "7"])

    def test_report_lists_every_entry(self):
        rows = [
            {"slug": "alpha", "baseline_tag": "v1", "expected": "empty", "token": "present", "class": "behavior-changed"},
            {"slug": "beta", "baseline_tag": "v1", "expected": "x", "token": "x", "class": "match"},
        ]
        report = watch.render_report("v2", DIGEST_NEW, rows, "https://example.com/run/1")
        self.assertIn("| alpha | v1 | `empty` | `present` | behavior-changed |", report)
        self.assertIn("| beta |", report)
        self.assertIn("https://example.com/run/1", report)


class MainTests(WatchCase):
    def run_main(self, argv, **kwargs):
        out, err = io.StringIO(), io.StringIO()
        published = []
        kwargs.setdefault("publish", lambda title, report: published.append(title) or ("created", None))
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = watch.main(argv + ["--root", str(self.root), "--report", str(self.root / "report.md")], env={}, **kwargs)
        return code, out.getvalue(), published

    def test_zero_entries_exits_clean_without_an_issue(self):
        code, out, published = self.run_main(["--open-issue"], latest=lambda token=None: "v2.0.0", resolver=self.resolver)
        self.assertEqual(code, 0)
        self.assertEqual(published, [])
        self.assertIn("0 entries ran", out)

    def test_prerelease_exits_clean(self):
        code, out, _ = self.run_main([], latest=lambda token=None: None)
        self.assertEqual(code, 0)
        self.assertIn("nothing to do", out)

    def test_a_change_opens_one_issue_and_exits_zero(self):
        self.add_entry("alpha", {"v1.0.0": "empty"})
        code, _, published = self.run_main(
            ["--tag", "v2.0.0", "--open-issue"], runner=self.runner_with({"alpha": "present"}), resolver=self.resolver
        )
        self.assertEqual(code, 0)
        self.assertEqual(published, ["Behavior change on v2.0.0"])
        self.assertTrue((self.root / "report.md").is_file())

    def test_a_change_without_open_issue_fails(self):
        self.add_entry("alpha", {"v1.0.0": "empty"})
        code, _, published = self.run_main(
            ["--tag", "v2.0.0"], runner=self.runner_with({"alpha": "present"}), resolver=self.resolver
        )
        self.assertEqual(code, 1)
        self.assertEqual(published, [])

    def test_all_matching_exits_zero_without_an_issue(self):
        self.add_entry("alpha", {"v1.0.0": "empty"})
        code, _, published = self.run_main(
            ["--tag", "v2.0.0", "--open-issue"], runner=self.runner_with({"alpha": "empty"}), resolver=self.resolver
        )
        self.assertEqual(code, 0)
        self.assertEqual(published, [])


if __name__ == "__main__":
    unittest.main()
