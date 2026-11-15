import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

from harness import stamp, validate_entries

DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64
RUN = "https://github.com/example/casebook/actions/runs/1"

ENTRY = """---
id: E3
slug: sample-entry
title: Enable the sample toolset before relying on it
kind: gotcha
status: open
affected:
  - v1.0.0
not_affected:
  - v1.1.0
fixed_in: null
upstream: none-found
searched_on: 2026-11-13
evidence:
  - https://example.com/org/repo/blob/0123456789abcdef0123456789abcdef01234567/src/main.py#L10
repro: entries/sample-entry/repro.sh
needs_credentials: false
confidence: source-verified
verified_on: []
last_reviewed: 2026-11-13
limits: Read in the source only.
credits: []
---

## Observation

Something.

## Hypothesis

Something is expected.

## Method

Run it.

## Results

### Runs

No CI run has been recorded yet.

### Expected and observed

Expected.

## Analysis

Cause.

## Recommendation

Workaround.

## Related work

None.

## Threats to validity

Limits.
"""


def fake_metadata(run_id, repository=None):
    return {
        "head_sha": "0123456789abcdef0123456789abcdef01234567",
        "head_branch": "main",
        "event": "workflow_dispatch",
        "created_at": "2026-11-14T01:00:00Z",
        "html_url": f"https://github.com/example/casebook/actions/runs/{run_id}",
        "name": "repro",
    }


def result(tag, token, digest, run_url=RUN, outcome="match", slug="sample-entry"):
    return {
        "slug": slug,
        "tag": tag,
        "digest": digest,
        "token": token,
        "expected": token,
        "class": outcome,
        "duration_s": 1.0,
        "runner": "Linux-X64",
        "timestamp_utc": "2026-11-14T01:02:03Z",
        "run_url": run_url,
    }


class StampCase(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "harness").mkdir()
        (self.root / "harness" / "images.json").write_text(json.dumps({
            "image": "example/hermes",
            "tags": {
                "v1.0.0": {"digest": DIGEST_A, "published": "2026-01-01"},
                "v1.1.0": {"digest": DIGEST_B, "published": "2026-02-01"},
            },
        }))
        self.entry = self.root / "entries" / "sample-entry"
        self.entry.mkdir(parents=True)
        (self.entry / "README.md").write_text(ENTRY)
        (self.entry / "expect.json").write_text(json.dumps({"v1.0.0": "empty", "v1.1.0": "present"}))
        repro = self.entry / "repro.sh"
        repro.write_text("#!/usr/bin/env bash\nset -euo pipefail\necho OBSERVED=empty\n")
        repro.chmod(0o755)

    def front(self):
        front, _ = stamp.split_entry((self.entry / "README.md").read_text())
        return front

    def body(self):
        return stamp.split_entry((self.entry / "README.md").read_text())[1]


class StampEntryTests(StampCase):
    def test_partial_coverage_records_the_run_but_keeps_source_verified(self):
        stamp.stamp(self.root, [result("v1.0.0", "empty", DIGEST_A)])
        front = self.front()
        self.assertEqual(front["confidence"], "source-verified")
        self.assertEqual(
            front["verified_on"],
            [{"tag": "v1.0.0", "digest": DIGEST_A, "date": "2026-11-14", "observed": "empty", "run": RUN}],
        )

    def test_full_coverage_marks_the_entry_reproduced(self):
        stamp.stamp(self.root, [result("v1.1.0", "present", DIGEST_B), result("v1.0.0", "empty", DIGEST_A)])
        front = self.front()
        self.assertEqual(front["confidence"], "reproduced")
        self.assertEqual([item["tag"] for item in front["verified_on"]], ["v1.0.0", "v1.1.0"])

    def test_a_newer_run_replaces_the_stamp_for_the_same_tag(self):
        stamp.stamp(self.root, [result("v1.0.0", "empty", DIGEST_A)])
        newer = dict(result("v1.0.0", "empty", DIGEST_A), run_url=RUN + "0", timestamp_utc="2026-12-01T00:00:00Z")
        stamp.stamp(self.root, [newer])
        self.assertEqual(self.front()["verified_on"][0]["run"], RUN + "0")
        self.assertEqual(len(self.front()["verified_on"]), 1)

    def test_non_matching_results_are_not_stamped(self):
        stamped, skipped = stamp.stamp(self.root, [result("v1.0.0", "present", DIGEST_A, outcome="behavior-changed")])
        self.assertEqual(stamped, [])
        self.assertEqual(len(skipped), 1)
        self.assertEqual(self.front()["verified_on"], [])

    def test_local_results_without_a_run_url_are_refused(self):
        with self.assertRaisesRegex(stamp.StampError, "CI run URL"):
            stamp.stamp(self.root, [result("v1.0.0", "empty", DIGEST_A, run_url=None)])
        self.assertEqual(self.front()["verified_on"], [])

    def test_a_digest_that_is_not_pinned_is_refused(self):
        with self.assertRaisesRegex(stamp.StampError, "not the one pinned"):
            stamp.stamp(self.root, [result("v1.0.0", "empty", DIGEST_B)])

    def test_nothing_is_written_when_one_result_is_invalid(self):
        before = (self.entry / "README.md").read_text()
        with self.assertRaises(stamp.StampError):
            stamp.stamp(self.root, [result("v1.0.0", "empty", DIGEST_A), result("v1.1.0", "present", DIGEST_B, slug="missing")])
        self.assertEqual((self.entry / "README.md").read_text(), before)

    def test_the_runs_section_becomes_a_table(self):
        stamp.stamp(self.root, [result("v1.0.0", "empty", DIGEST_A)])
        body = self.body()
        self.assertIn("| v1.0.0 | `empty` | 2026-11-14 |", body)
        self.assertIn(f"[run]({RUN})", body)
        self.assertIn("### Expected and observed\n\nExpected.", body)
        self.assertIn("## Method", body)
        self.assertNotIn("No CI run has been recorded yet.", body)

    def test_other_front_matter_is_kept(self):
        stamp.stamp(self.root, [result("v1.0.0", "empty", DIGEST_A)])
        front = self.front()
        self.assertEqual(front["upstream"], "none-found")
        self.assertEqual(str(front["searched_on"]), "2026-11-13")
        self.assertEqual(list(front)[:3], ["id", "slug", "title"])

    def test_a_stamped_entry_still_validates(self):
        stamp.stamp(self.root, [result("v1.1.0", "present", DIGEST_B), result("v1.0.0", "empty", DIGEST_A)])
        report = validate_entries.validate(
            self.root, self.root / "entries", self.root / "harness" / "images.json",
            __import__("datetime").date(2026, 11, 14),
        )
        self.assertEqual([finding.line() for finding in report.violations], [])


class IndexTests(StampCase):
    def test_index_lists_every_entry(self):
        stamp.stamp(self.root, [])
        index = (self.root / "INDEX.md").read_text()
        self.assertIn("| E3 | [Enable the sample toolset before relying on it](entries/sample-entry/README.md) |", index)
        self.assertIn("| not yet |", index)

    def test_index_shows_the_last_verification_date(self):
        stamp.stamp(self.root, [result("v1.0.0", "empty", DIGEST_A)])
        self.assertIn("| 2026-11-14 |", (self.root / "INDEX.md").read_text())

    def test_empty_repository_index(self):
        (self.entry / "README.md").unlink()
        stamp.stamp(self.root, [])
        self.assertTrue((self.root / "INDEX.md").read_text().endswith("No entries yet.\n"))

    def test_entries_are_sorted_by_numeric_id(self):
        for number in (10, 2):
            other = self.root / "entries" / f"other-{number}"
            other.mkdir()
            (other / "README.md").write_text(ENTRY.replace("id: E3", f"id: E{number}"))
        fronts = stamp.entry_fronts(self.root / "entries")
        self.assertEqual([front["id"] for front in fronts], ["E2", "E3", "E10"])


class MainTests(StampCase):
    def run_main(self, argv, download=None):
        out, err = io.StringIO(), io.StringIO()
        options = {"metadata": fake_metadata}
        if download:
            options["download"] = download
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = stamp.main(argv + ["--root", str(self.root)], **options)
        return code, out.getvalue(), err.getvalue()

    def test_run_mode_downloads_then_stamps(self):
        calls = []

        def fake_download(run_id, destination, repository):
            calls.append((run_id, repository))
            target = Path(destination) / "results-v1.0.0" / "sample-entry"
            target.mkdir(parents=True)
            (target / "v1.0.0.json").write_text(json.dumps(result("v1.0.0", "empty", DIGEST_A)))
            (target / "v1.0.0.log").write_text("EVIDENCE skills_index chars 0\n")

        code, out, _ = self.run_main(["--run", "1", "--repo", "example/casebook"], fake_download)
        self.assertEqual(code, 0)
        self.assertEqual(calls, [("1", "example/casebook")])
        self.assertIn("stamped sample-entry", out)
        evidence = self.root / "evidence" / "1"
        self.assertEqual((evidence / "sample-entry" / "v1.0.0.log").read_text(), "EVIDENCE skills_index chars 0\n")
        readme = (evidence / "README.md").read_text()
        self.assertIn("0123456789abcdef", readme)
        self.assertIn("- Run: <https://github.com/example/casebook/actions/runs/1>", readme)
        sums = (evidence / "SHA256SUMS").read_text()
        self.assertIn("  sample-entry/v1.0.0.json\n", sums)
        self.assertIn("  README.md\n", sums)
        entry = (self.root / "entries" / "sample-entry" / "README.md").read_text()
        self.assertIn("[log](../../evidence/1/sample-entry/v1.0.0.log)", entry)

    def test_run_mode_refuses_results_from_another_run(self):
        def fake_download(run_id, destination, repository):
            target = Path(destination) / "results-v1.0.0" / "sample-entry"
            target.mkdir(parents=True)
            (target / "v1.0.0.json").write_text(json.dumps(result("v1.0.0", "empty", DIGEST_A)))

        code, _, err = self.run_main(["--run", "42"], fake_download)
        self.assertEqual(code, 2)
        self.assertIn("not only from", err)
        self.assertFalse((self.root / "evidence").exists())

    def test_a_stamp_without_committed_evidence_shows_no_transcript(self):
        section = stamp.verified_section([stamp.verified_item(result("v1.0.0", "empty", DIGEST_A))], self.root, "sample-entry")
        self.assertIn("| none |", section)

    def test_index_only(self):
        code, _, _ = self.run_main(["--index-only"])
        self.assertEqual(code, 0)
        self.assertTrue((self.root / "INDEX.md").is_file())

    def test_errors_exit_two(self):
        results = self.root / "results"
        (results / "sample-entry").mkdir(parents=True)
        (results / "sample-entry" / "v1.0.0.json").write_text(json.dumps(result("v1.0.0", "empty", DIGEST_A, run_url=None)))
        code, _, err = self.run_main(["--results", str(results)])
        self.assertEqual(code, 2)
        self.assertIn("error:", err)


class DownloadTests(unittest.TestCase):
    def fake_gh(self, artifact_names):
        calls = []

        def run(command, **kwargs):
            calls.append(command)
            stdout = "\n".join(artifact_names) if command[:2] == ["gh", "api"] else ""
            return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")
        return run, calls

    def test_a_run_without_result_artifacts_downloads_nothing(self):
        run, calls = self.fake_gh(["smoke-v1.0.0", "smoke-v1.1.0"])
        stamp.download_run("7", "/tmp/unused", None, run)
        self.assertEqual([command[:2] for command in calls], [["gh", "api"]])
        self.assertIn("repos/{owner}/{repo}/actions/runs/7/artifacts", calls[0])

    def test_result_artifacts_are_downloaded(self):
        run, calls = self.fake_gh(["smoke-v1.0.0", "results-v1.0.0"])
        stamp.download_run("7", "/tmp/target", "example/casebook", run)
        self.assertIn("repos/example/casebook/actions/runs/7/artifacts", calls[0])
        self.assertEqual(calls[1][:4], ["gh", "run", "download", "7"])
        self.assertEqual(calls[1][-2:], ["--repo", "example/casebook"])


class FrontMatterTests(unittest.TestCase):
    def test_round_trip_keeps_values(self):
        front, body = stamp.split_entry(ENTRY)
        again, again_body = stamp.split_entry(stamp.join_entry(front, body))
        self.assertEqual(front, again)
        self.assertEqual(body, again_body)
        self.assertEqual(yaml.safe_load(stamp.dump_front(front))["slug"], "sample-entry")

    def test_missing_front_matter_is_an_error(self):
        with self.assertRaises(stamp.StampError):
            stamp.split_entry("# no front matter\n")


if __name__ == "__main__":
    unittest.main()
