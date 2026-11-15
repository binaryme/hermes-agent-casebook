import contextlib
import datetime
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from harness import validate_entries as validator

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "harness" / "validate_entries.py"
FIXTURES = REPO_ROOT / "tests" / "fixtures"
ENTRIES = FIXTURES / "entries"
IMAGES = FIXTURES / "images.json"
TODAY = datetime.date(2026, 11, 13)
FINDING_LINE = re.compile(r"^\S.*: [a-z-]+: .+$")


def check_one(entry_dir, today=TODAY):
    report = validator.Report()
    context = validator.Context(pinned_tags=validator.load_images(IMAGES, report), today=today)
    validator.check_entry(entry_dir, context, report)
    report.extend(validator.check_comment_lines(entry_dir))
    return report


def rules_of(report):
    return {finding.rule for finding in report.violations}


def warning_rules_of(report):
    return {finding.rule for finding in report.warnings}


def clone_good_entry(entries_dir, slug, replacements=()):
    target = entries_dir / slug
    shutil.copytree(ENTRIES / "good", target)
    readme = target / "README.md"
    text = readme.read_text(encoding="utf-8")
    text = text.replace("slug: good", f"slug: {slug}").replace("entries/good/", f"entries/{slug}/")
    for old, new in replacements:
        if old not in text:
            raise AssertionError(f"{old!r} not found in the good fixture")
        text = text.replace(old, new)
    readme.write_text(text, encoding="utf-8")
    return target


def write_files(root, files):
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def run_main(arguments):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = validator.main(arguments)
    return code, out.getvalue(), err.getvalue()


class FixtureEntryTests(unittest.TestCase):
    def test_good_entry_has_no_findings(self):
        report = check_one(ENTRIES / "good")
        self.assertEqual([], report.violations)
        self.assertEqual([], report.warnings)

    def test_each_bad_fixture_violates_exactly_its_rule(self):
        bad = sorted(path for path in ENTRIES.iterdir() if path.name.startswith("bad-"))
        self.assertTrue(bad)
        for entry in bad:
            with self.subTest(entry=entry.name):
                self.assertEqual({entry.name.removeprefix("bad-")}, rules_of(check_one(entry)))

    def test_every_entry_rule_has_a_bad_fixture(self):
        fixture_rules = {
            path.name.removeprefix("bad-") for path in ENTRIES.iterdir() if path.name.startswith("bad-")
        }
        self.assertEqual(set(validator.ENTRY_RULES), fixture_rules)

    def test_fixture_repro_scripts_follow_their_modes(self):
        self.assertTrue((ENTRIES / "good" / "repro.sh").stat().st_mode & 0o111)
        self.assertFalse((ENTRIES / "bad-repro-not-executable" / "repro.sh").stat().st_mode & 0o111)


class EntryRuleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.entries = self.root / "entries"
        self.entries.mkdir()

    def validate(self, today=TODAY):
        return validator.validate(self.root, self.entries, IMAGES, today)

    def test_reproduced_entry_with_a_valid_verified_on_passes(self):
        verified = (
            "verified_on:\n  - tag: v9.0.0\n    digest: sha256:" + "a" * 64
            + "\n    date: 2026-11-13\n    observed: empty\n    run: https://example.com/runs/1"
        )
        clone_good_entry(
            self.entries,
            "reproduced-entry",
            [("confidence: source-verified", "confidence: reproduced"), ("verified_on: []", verified)],
        )
        report = self.validate()
        self.assertEqual([], report.violations)

    def test_none_found_with_searched_on_passes(self):
        clone_good_entry(
            self.entries,
            "no-upstream",
            [
                ("upstream:\n  - https://example.com/org/repo/issues/1", "upstream: none-found\nsearched_on: 2026-11-13"),
            ],
        )
        self.assertEqual([], self.validate().violations)

    def test_pointer_without_repro_may_be_source_verified(self):
        clone = clone_good_entry(
            self.entries,
            "documented-pointer",
            [("kind: gotcha", "kind: pointer"), ("repro: entries/documented-pointer/repro.sh", "repro: null")],
        )
        (clone / "repro.sh").unlink()
        (clone / "expect.json").unlink()
        self.assertEqual([], self.validate().violations)

    def test_duplicate_yaml_keys_are_rejected(self):
        clone_good_entry(self.entries, "twice", [("kind: gotcha", "kind: gotcha\nkind: pointer")])
        self.assertEqual({"front-matter"}, rules_of(self.validate()))

    def test_malformed_yaml_is_rejected(self):
        clone_good_entry(self.entries, "broken", [("kind: gotcha", "kind: [gotcha")])
        self.assertEqual({"front-matter"}, rules_of(self.validate()))

    def test_duplicate_id_across_entries_is_rejected(self):
        clone_good_entry(self.entries, "first")
        clone_good_entry(self.entries, "second")
        report = self.validate()
        self.assertEqual({"duplicate-id"}, rules_of(report))
        self.assertEqual(1, len(report.violations))
        self.assertIn("second", report.violations[0].path)

    def test_directory_without_readme_is_rejected(self):
        (self.entries / "empty-entry").mkdir()
        self.assertEqual({"readme-missing"}, rules_of(self.validate()))

    def test_entries_need_images_json(self):
        clone_good_entry(self.entries, "lonely")
        report = validator.validate(self.root, self.entries, self.root / "missing.json", TODAY)
        self.assertIn("images-missing", rules_of(report))

    def test_headings_inside_code_fences_are_ignored(self):
        clone = clone_good_entry(self.entries, "fenced")
        readme = clone / "README.md"
        fence = "`" * 3
        readme.write_text(
            readme.read_text(encoding="utf-8") + f"\n{fence}text\n## Not a heading\n{fence}\n",
            encoding="utf-8",
        )
        self.assertEqual([], self.validate().violations)

    def test_extra_and_missing_headings_are_both_named(self):
        clone = clone_good_entry(self.entries, "headed")
        readme = clone / "README.md"
        text = readme.read_text(encoding="utf-8").replace("## Analysis", "## Reason")
        readme.write_text(text, encoding="utf-8")
        messages = " ".join(finding.message for finding in self.validate().violations)
        self.assertIn("missing heading '## Analysis'", messages)
        self.assertIn("unexpected heading '## Reason'", messages)

    def test_duplicate_heading_is_rejected(self):
        clone = clone_good_entry(self.entries, "dupe-heading")
        readme = clone / "README.md"
        readme.write_text(readme.read_text(encoding="utf-8") + "\n## Observation\n\nAgain.\n", encoding="utf-8")
        self.assertEqual({"headings"}, rules_of(self.validate()))

    def test_results_need_a_runs_subsection(self):
        clone = clone_good_entry(self.entries, "no-runs")
        readme = clone / "README.md"
        readme.write_text(readme.read_text(encoding="utf-8").replace("### Runs", "### Table"), encoding="utf-8")
        messages = " ".join(finding.message for finding in self.validate().violations)
        self.assertIn("needs a '### Runs' subsection", messages)

    def test_literal_tag_shapes_are_rejected_even_when_unpinned(self):
        clone = clone_good_entry(self.entries, "tagged")
        script = clone / "repro.sh"
        script.write_text(script.read_text(encoding="utf-8") + "echo v1.2.3\n", encoding="utf-8")
        self.assertEqual({"repro-image-tag"}, rules_of(self.validate()))

    def test_repro_with_exactly_thirty_non_blank_lines_passes(self):
        clone = clone_good_entry(self.entries, "thirty")
        script = clone / "repro.sh"
        current = len([line for line in script.read_text(encoding="utf-8").splitlines() if line.strip()])
        filler = "".join(f"echo line-{n}\n\n" for n in range(30 - current))
        script.write_text(script.read_text(encoding="utf-8") + filler, encoding="utf-8")
        self.assertEqual([], self.validate().violations)


class WarningTests(unittest.TestCase):
    def test_review_older_than_sixty_days_warns_without_failing(self):
        report = check_one(ENTRIES / "good", today=TODAY + datetime.timedelta(days=61))
        self.assertEqual([], report.violations)
        self.assertEqual({"stale-review"}, warning_rules_of(report))

    def test_review_exactly_sixty_days_old_does_not_warn(self):
        report = check_one(ENTRIES / "good", today=TODAY + datetime.timedelta(days=60))
        self.assertEqual([], report.warnings)

    def test_unpinned_tag_warns_without_failing(self):
        with tempfile.TemporaryDirectory() as tmp:
            entries = Path(tmp) / "entries"
            entries.mkdir()
            clone_good_entry(entries, "unpinned", [("affected:\n  - v9.0.0", "affected:\n  - v9.0.0\n  - v7.7.7")])
            report = validator.validate(Path(tmp), entries, IMAGES, TODAY)
        self.assertEqual([], report.violations)
        self.assertEqual({"tag-not-pinned"}, warning_rules_of(report))


class ImagesFileTests(unittest.TestCase):
    def validate_images(self, content):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "images.json"
            path.write_text(content, encoding="utf-8")
            report = validator.Report()
            pinned = validator.load_images(path, report)
        return pinned, report

    def test_fixture_images_file_is_valid(self):
        pinned, report = self.validate_images(IMAGES.read_text(encoding="utf-8"))
        self.assertEqual([], report.violations)
        self.assertEqual(frozenset({"v9.0.0", "v9.1.0", "v9.2.0"}), pinned)

    def test_invalid_shapes_are_rejected(self):
        good_record = {"digest": "sha256:" + "a" * 64, "published": "2026-01-01"}
        cases = {
            "not json": "{",
            "wrong keys": json.dumps({"image": "x"}),
            "tags not object": json.dumps({"image": "x", "tags": []}),
            "short digest": json.dumps({"image": "x", "tags": {"v1.0.0": {**good_record, "digest": "sha256:abc"}}}),
            "bad date": json.dumps({"image": "x", "tags": {"v1.0.0": {**good_record, "published": "yesterday"}}}),
            "extra key": json.dumps({"image": "x", "tags": {"v1.0.0": {**good_record, "size": 1}}}),
            "bad tag": json.dumps({"image": "x", "tags": {"has space": good_record}}),
        }
        for name, content in cases.items():
            with self.subTest(case=name):
                pinned, report = self.validate_images(content)
                self.assertIsNone(pinned)
                self.assertEqual({"images-invalid"}, rules_of(report))

    def test_missing_images_file_is_not_a_violation_by_itself(self):
        report = validator.Report()
        self.assertIsNone(validator.load_images(Path("does-not-exist.json"), report))
        self.assertEqual([], report.violations)


class CommentLineTests(unittest.TestCase):
    def scan(self, files):
        with tempfile.TemporaryDirectory() as tmp:
            write_files(Path(tmp), files)
            report = validator.check_comment_lines(tmp)
        return sorted((finding.path, finding.message) for finding in report.violations)

    def test_comment_lines_are_found_in_every_scanned_suffix(self):
        files = {
            "a.sh": "set -e\n  # indented comment\n",
            "b.py": "value = 1\n# comment\n",
            "c.yml": "key: 1\n# comment\n",
            "d.yaml": "# comment\nkey: 1\n",
            "e.toml": "key = 1\n# comment\n",
        }
        found = self.scan(files)
        self.assertEqual(
            [
                ("a.sh", "line 2 is a comment"),
                ("b.py", "line 2 is a comment"),
                ("c.yml", "line 2 is a comment"),
                ("d.yaml", "line 1 is a comment"),
                ("e.toml", "line 2 is a comment"),
            ],
            found,
        )

    def test_shebang_on_the_first_line_is_allowed(self):
        files = {"run.sh": "#!/usr/bin/env bash\nset -e\n", "tool.py": "#!/usr/bin/env python3\nvalue = 1\n"}
        self.assertEqual([], self.scan(files))

    def test_shebang_anywhere_else_is_a_comment(self):
        self.assertEqual([("late.sh", "line 2 is a comment")], self.scan({"late.sh": "set -e\n#!/usr/bin/env bash\n"}))

    def test_python_inline_comments_are_found(self):
        self.assertEqual([("x.py", "line 1 is a comment")], self.scan({"x.py": "value = 1  # inline\n"}))

    def test_python_strings_that_contain_hashes_are_not_comments(self):
        source = "\n".join(
            [
                'TEXT = """',
                "# looks like a comment but is data",
                '"""',
                'HEADING = "## Symptom"',
                "",
            ]
        )
        self.assertEqual([], self.scan({"data.py": source}))

    def test_unparsable_python_falls_back_to_the_line_rule(self):
        self.assertEqual([("broken.py", "line 2 is a comment")], self.scan({"broken.py": "def (:\n# note\n"}))

    def test_other_suffixes_are_ignored(self):
        files = {"README.md": "# Title\n", "notes.txt": "# note\n", "data.json": "{}\n"}
        self.assertEqual([], self.scan(files))

    def test_fixture_directories_are_exempt(self):
        files = {
            "tests/fixtures/entries/x/repro.sh": "# fixture\n",
            "entries/some-slug/fixtures/config.yaml": "# fixture\nkey: 1\n",
            "entries/some-slug/repro.sh": "set -e\n# not a fixture\n",
        }
        self.assertEqual([("entries/some-slug/repro.sh", "line 2 is a comment")], self.scan(files))

    def test_tooling_directories_are_pruned(self):
        files = {".git/hooks/pre-commit.sh": "# hook\n", ".venv/lib/x.py": "# vendored\n", "node_modules/y.py": "# vendored\n"}
        self.assertEqual([], self.scan(files))


class HelperTests(unittest.TestCase):
    def test_sentence_counting(self):
        self.assertEqual(1, validator.count_sentences("One sentence only."))
        self.assertEqual(2, validator.count_sentences("First. Second sentence here."))
        self.assertEqual(1, validator.count_sentences("Seen on v0.23.1 only, e.g. the Docker image."))
        self.assertEqual(1, validator.count_sentences("No final period"))
        self.assertEqual(3, validator.count_sentences("One. Two! Three?"))

    def test_front_matter_splitting(self):
        raw, body = validator.split_front_matter("---\na: 1\n---\n## Symptom\n")
        self.assertEqual("a: 1", raw)
        self.assertEqual("## Symptom", body)
        self.assertIsNone(validator.split_front_matter("no front matter")[0])
        self.assertIsNone(validator.split_front_matter("---\nnever closed\n")[0])

    def test_headings_skip_fences_and_deeper_levels(self):
        fence = "`" * 3
        body = f"# Title\n## One\n### Deeper\n{fence}\n## Hidden\n{fence}\n## Two\n"
        self.assertEqual(["One", "Two"], validator.body_headings(body))

    def test_literal_tags(self):
        self.assertEqual({"v1.2.3"}, validator.literal_tags("echo v1.2.3", set()))
        self.assertEqual(set(), validator.literal_tags("post_v2 route payload", set()))
        self.assertEqual({"nightly"}, validator.literal_tags("run nightly now", {"nightly"}))
        self.assertEqual(set(), validator.literal_tags("run nightlyish now", {"nightly"}))

    def test_dates(self):
        self.assertEqual(datetime.date(2026, 11, 13), validator.as_date("2026-11-13"))
        self.assertEqual(datetime.date(2026, 11, 13), validator.as_date(datetime.date(2026, 11, 13)))
        self.assertIsNone(validator.as_date("2026-13-40"))
        self.assertIsNone(validator.as_date("20261113"))
        self.assertIsNone(validator.as_date(datetime.datetime(2026, 11, 13, 1, 2)))
        self.assertIsNone(validator.as_date(None))


class CommandLineTests(unittest.TestCase):
    def test_missing_entries_directory_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, _ = run_main(
                ["--entries-dir", str(Path(tmp) / "entries"), "--images", str(Path(tmp) / "images.json"), "--root", tmp]
            )
        self.assertEqual((0, ""), (code, out))

    def test_empty_entries_directory_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "entries").mkdir()
            code, out, _ = run_main(
                ["--entries-dir", str(Path(tmp) / "entries"), "--images", str(Path(tmp) / "images.json"), "--root", tmp]
            )
        self.assertEqual((0, ""), (code, out))

    def test_violations_print_one_line_each_and_exit_one(self):
        code, out, _ = run_main(
            [
                "--entries-dir",
                str(ENTRIES),
                "--images",
                str(IMAGES),
                "--root",
                str(ENTRIES / "good"),
            ]
        )
        lines = out.splitlines()
        self.assertEqual(1, code)
        self.assertTrue(lines)
        for line in lines:
            with self.subTest(line=line):
                self.assertRegex(line, FINDING_LINE)
        self.assertIn("bad-enum/README.md: enum:", out)

    def test_clean_entries_exit_zero_and_warnings_go_to_stderr(self):
        with tempfile.TemporaryDirectory() as tmp:
            entries = Path(tmp) / "entries"
            entries.mkdir()
            clone_good_entry(entries, "stale", [("last_reviewed: 2026-11-13", "last_reviewed: 2020-01-01")])
            code, out, err = run_main(["--entries-dir", str(entries), "--images", str(IMAGES), "--root", tmp])
        self.assertEqual((0, ""), (code, out))
        self.assertIn("warning: ", err)
        self.assertIn("stale-review", err)

    def test_script_runs_as_a_program_from_the_repository_root(self):
        completed = subprocess.run(
            [sys.executable, "-I", str(SCRIPT)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertEqual("", completed.stdout)


if __name__ == "__main__":
    unittest.main()
