import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from harness import plan_matrix

EXPECTATIONS = {
    "alpha-entry": ["v1", "v2"],
    "beta-entry": ["v2", "v3"],
    "gamma-entry": ["v3"],
}
TAG_ORDER = ["v1", "v2", "v3"]


class ChangedPathsTests(unittest.TestCase):
    def test_splits_on_nul_and_drops_empty_items(self):
        self.assertEqual(
            plan_matrix.changed_paths_from_diff("a/b.md\0entries/x/README.md\0"),
            ["a/b.md", "entries/x/README.md"],
        )

    def test_empty_diff(self):
        self.assertEqual(plan_matrix.changed_paths_from_diff(""), [])

    def test_diff_paths_asks_git_for_the_merge_base_range(self):
        calls = []

        def fake_run(command, **options):
            calls.append((command, options))
            return SimpleNamespace(stdout="entries/alpha-entry/README.md\0")

        paths = plan_matrix.diff_paths("/repo", "base123", "head456", run=fake_run)
        command, options = calls[0]
        self.assertEqual(paths, ["entries/alpha-entry/README.md"])
        self.assertEqual(command[:2], ["git", "diff"])
        self.assertIn("base123...head456", command)
        self.assertIn("-z", command)
        self.assertEqual(options["cwd"], "/repo")


class SelectionTests(unittest.TestCase):
    def test_harness_and_workflow_changes_select_everything(self):
        for path in ("harness/run_repro.py", "harness/lib.sh", ".github/workflows/repro.yml"):
            with self.subTest(path=path):
                self.assertTrue(plan_matrix.selects_every_entry(path))

    def test_chatwoot_guide_code_selects_everything_but_prose_does_not(self):
        self.assertTrue(plan_matrix.selects_every_entry("guides/chatwoot/relay/relay.py"))
        self.assertTrue(plan_matrix.selects_every_entry("guides/chatwoot/e2e.sh"))
        self.assertFalse(plan_matrix.selects_every_entry("guides/chatwoot/README.md"))

    def test_other_paths_do_not_select_everything(self):
        for path in ("README.md", "docs/harness.md", "tests/test_x.py", "entries/a/README.md"):
            with self.subTest(path=path):
                self.assertFalse(plan_matrix.selects_every_entry(path))

    def test_entry_slug_of(self):
        self.assertEqual(plan_matrix.entry_slug_of("entries/alpha-entry/fixtures/a.yaml"), "alpha-entry")
        self.assertEqual(plan_matrix.entry_slug_of("entries/alpha-entry/repro.sh"), "alpha-entry")
        self.assertIsNone(plan_matrix.entry_slug_of("entries/README.md"))
        self.assertIsNone(plan_matrix.entry_slug_of("docs/entries/alpha-entry/x"))

    def test_changed_entry_selects_only_itself(self):
        self.assertEqual(
            plan_matrix.selected_slugs(["entries/beta-entry/README.md"], EXPECTATIONS),
            {"beta-entry"},
        )

    def test_unknown_or_deleted_entries_are_ignored(self):
        self.assertEqual(
            plan_matrix.selected_slugs(["entries/gone/README.md", "README.md"], EXPECTATIONS),
            set(),
        )


class MatrixTests(unittest.TestCase):
    def test_one_changed_entry_runs_only_its_tags(self):
        matrix = plan_matrix.plan_from_paths(
            ["entries/alpha-entry/repro.sh"], EXPECTATIONS, TAG_ORDER
        )
        self.assertEqual(
            matrix,
            {
                "include": [
                    {"tag": "v1", "entries": ["alpha-entry"]},
                    {"tag": "v2", "entries": ["alpha-entry"]},
                ]
            },
        )

    def test_entries_sharing_a_tag_are_grouped_under_it(self):
        matrix = plan_matrix.plan_from_paths(
            ["entries/gamma-entry/README.md", "entries/beta-entry/README.md"],
            EXPECTATIONS,
            TAG_ORDER,
        )
        self.assertEqual(
            matrix,
            {
                "include": [
                    {"tag": "v2", "entries": ["beta-entry"]},
                    {"tag": "v3", "entries": ["beta-entry", "gamma-entry"]},
                ]
            },
        )

    def test_harness_change_runs_every_entry_on_every_tag(self):
        matrix = plan_matrix.plan_from_paths(["harness/lib.sh"], EXPECTATIONS, TAG_ORDER)
        self.assertEqual(
            matrix,
            {
                "include": [
                    {"tag": "v1", "entries": ["alpha-entry"]},
                    {"tag": "v2", "entries": ["alpha-entry", "beta-entry"]},
                    {"tag": "v3", "entries": ["beta-entry", "gamma-entry"]},
                ]
            },
        )

    def test_docs_only_change_plans_nothing(self):
        self.assertEqual(
            plan_matrix.plan_from_paths(["README.md", "docs/harness.md"], EXPECTATIONS, TAG_ORDER),
            {"include": []},
        )

    def test_no_entries_plans_nothing_even_for_harness_changes(self):
        self.assertEqual(plan_matrix.plan_from_paths(["harness/lib.sh"], {}, TAG_ORDER), {"include": []})

    def test_tags_follow_the_pinned_order_then_alphabetical(self):
        order = ["v3", "v1"]
        matrix = plan_matrix.plan_from_paths(["harness/lib.sh"], EXPECTATIONS, order)
        self.assertEqual([item["tag"] for item in matrix["include"]], ["v3", "v1", "v2"])

    def test_dispatch_filters(self):
        self.assertEqual(
            plan_matrix.plan_everything(EXPECTATIONS, TAG_ORDER, entry_filter="beta-entry"),
            {
                "include": [
                    {"tag": "v2", "entries": ["beta-entry"]},
                    {"tag": "v3", "entries": ["beta-entry"]},
                ]
            },
        )
        self.assertEqual(
            plan_matrix.plan_everything(EXPECTATIONS, TAG_ORDER, tag_filter="v2"),
            {"include": [{"tag": "v2", "entries": ["alpha-entry", "beta-entry"]}]},
        )
        self.assertEqual(
            plan_matrix.plan_everything(EXPECTATIONS, TAG_ORDER, "alpha-entry", "v1"),
            {"include": [{"tag": "v1", "entries": ["alpha-entry"]}]},
        )

    def test_dispatch_without_filters_runs_everything(self):
        matrix = plan_matrix.plan_everything(EXPECTATIONS, TAG_ORDER)
        self.assertEqual([item["tag"] for item in matrix["include"]], ["v1", "v2", "v3"])

    def test_dispatch_with_unknown_entry_is_an_error(self):
        with self.assertRaises(plan_matrix.PlanError):
            plan_matrix.plan_everything(EXPECTATIONS, TAG_ORDER, entry_filter="ghost")

    def test_dispatch_with_a_tag_the_entry_does_not_expect_is_an_error(self):
        with self.assertRaises(plan_matrix.PlanError):
            plan_matrix.plan_everything(EXPECTATIONS, TAG_ORDER, "alpha-entry", "v3")

    def test_dispatch_on_a_repo_without_entries_is_not_an_error(self):
        self.assertEqual(plan_matrix.plan_everything({}, TAG_ORDER), {"include": []})


class GithubOutputTests(unittest.TestCase):
    def test_with_work(self):
        matrix = {"include": [{"tag": "v1", "entries": ["a"]}]}
        self.assertEqual(
            plan_matrix.format_github_output(matrix),
            'matrix={"include":[{"tag":"v1","entries":["a"]}]}\nhas_work=true\n',
        )

    def test_without_work(self):
        self.assertEqual(
            plan_matrix.format_github_output({"include": []}),
            'matrix={"include":[]}\nhas_work=false\n',
        )


class RepoFixtureCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "harness").mkdir()
        images = {"image": "example/hermes", "tags": {tag: {"digest": "sha256:" + "0" * 64} for tag in TAG_ORDER}}
        (self.root / "harness" / "images.json").write_text(json.dumps(images), encoding="utf-8")
        for slug, tags in EXPECTATIONS.items():
            entry = self.root / "entries" / slug
            entry.mkdir(parents=True)
            (entry / "expect.json").write_text(json.dumps({tag: "token" for tag in tags}), encoding="utf-8")
        (self.root / "entries" / "no-expectations").mkdir()
        (self.root / "entries" / "Bad Name").mkdir()
        (self.root / "entries" / "Bad Name" / "expect.json").write_text('{"v1": "x"}', encoding="utf-8")
        (self.root / "entries" / "README.md").write_text("index\n", encoding="utf-8")


class LoadingTests(RepoFixtureCase):
    def test_loads_expectations_for_valid_entries_only(self):
        self.assertEqual(plan_matrix.load_expectations(self.root), EXPECTATIONS)

    def test_missing_entries_directory_is_empty(self):
        self.assertEqual(plan_matrix.load_expectations(self.root / "nowhere"), {})

    def test_tag_order_follows_images_json(self):
        self.assertEqual(plan_matrix.load_tag_order(self.root), TAG_ORDER)

    def test_missing_images_file_gives_no_order(self):
        self.assertEqual(plan_matrix.load_tag_order(self.root / "nowhere"), [])


class MainTests(RepoFixtureCase):
    def call(self, *args):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = plan_matrix.main([*args, "--root", str(self.root)])
        return code, stdout.getvalue(), stderr.getvalue()

    def test_paths_mode_prints_the_matrix(self):
        code, out, _ = self.call("--paths", "entries/gamma-entry/README.md")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), {"include": [{"tag": "v3", "entries": ["gamma-entry"]}]})

    def test_empty_paths_print_an_empty_matrix(self):
        code, out, _ = self.call("--paths")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), {"include": []})

    def test_all_mode_with_filters(self):
        code, out, _ = self.call("--all", "--entry", "beta-entry", "--tag", "v3")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), {"include": [{"tag": "v3", "entries": ["beta-entry"]}]})

    def test_all_mode_with_unknown_entry_fails(self):
        code, _, err = self.call("--all", "--entry", "ghost")
        self.assertEqual(code, 2)
        self.assertIn("ghost", err)

    def test_base_without_head_fails(self):
        code, _, _ = self.call("--base", "abc")
        self.assertEqual(code, 2)

    def test_writes_github_output_file(self):
        output_file = self.root / "github-output.txt"
        previous = os.environ.get("GITHUB_OUTPUT")
        os.environ["GITHUB_OUTPUT"] = str(output_file)
        try:
            code, _, _ = self.call("--paths", "harness/lib.sh", "--github-output")
        finally:
            if previous is None:
                del os.environ["GITHUB_OUTPUT"]
            else:
                os.environ["GITHUB_OUTPUT"] = previous
        self.assertEqual(code, 0)
        lines = output_file.read_text(encoding="utf-8").splitlines()
        self.assertTrue(lines[0].startswith("matrix="))
        self.assertEqual(lines[1], "has_work=true")
        self.assertEqual(
            [item["tag"] for item in json.loads(lines[0][len("matrix="):])["include"]],
            TAG_ORDER,
        )


if __name__ == "__main__":
    unittest.main()
