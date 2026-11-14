#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness import resolve_digest, run_repro

ROOT = run_repro.ROOT
LATEST_URL = "https://api.github.com/repos/{repository}/releases/latest"
SKIPPED_TAG_PATTERN = re.compile(r"canary|nightly|-rc", re.IGNORECASE)


class WatchError(Exception):
    pass


def latest_release(fetch=resolve_digest.http_get, token=None):
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    status, _, body = fetch(LATEST_URL.format(repository=resolve_digest.UPSTREAM_REPOSITORY), headers)
    if status != 200:
        raise WatchError(f"the latest upstream release answered HTTP {status}")
    release = json.loads(body)
    tag = release.get("tag_name", "")
    if release.get("prerelease") or release.get("draft") or SKIPPED_TAG_PATTERN.search(tag):
        return None
    return tag or None


def newest_expectation(expectations, tag_order):
    for tag in reversed(tag_order):
        if tag in expectations:
            return tag, expectations[tag]
    return None, None


def entry_baselines(root, tag_order):
    baselines = {}
    entries_dir = Path(root) / "entries"
    if not entries_dir.is_dir():
        return baselines
    for expect_path in sorted(entries_dir.glob("*/expect.json")):
        expectations = json.loads(expect_path.read_text(encoding="utf-8"))
        baseline_tag, token = newest_expectation(expectations, tag_order)
        if token is not None:
            baselines[expect_path.parent.name] = (baseline_tag, token)
    return baselines


def run_all(root, tag, images_path, baselines, results_dir, runner=run_repro.run_entry):
    rows = []
    for slug, (baseline_tag, token) in sorted(baselines.items()):
        try:
            result, _, _ = runner(
                slug, tag, root=root, images_path=images_path, results_dir=results_dir, expect_override=token
            )
        except run_repro.ConfigError as error:
            result = {"slug": slug, "token": None, "class": run_repro.REPRO_ERROR, "reason": str(error)}
        rows.append({
            "slug": slug,
            "baseline_tag": baseline_tag,
            "expected": token,
            "token": result.get("token"),
            "class": result["class"],
        })
    return rows


def changed_rows(rows):
    return [row for row in rows if row["class"] != run_repro.MATCH]


def issue_title(tag):
    return f"Behavior change on {tag}"


def render_report(tag, digest, rows, run_url):
    lines = [
        f"Hermes `{tag}` (`{digest}`) gave a different result than the newest pinned tag for at least one entry.",
        "",
        "| Entry | Baseline tag | Expected | Observed | Class |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['slug']} | {row['baseline_tag']} | `{row['expected']}` | `{row['token']}` | {row['class']} |"
        )
    lines += ["", f"Run and artifacts: {run_url or 'local run, no URL'}", ""]
    lines.append("A maintainer adds the tag to `harness/images.json`, updates `expect.json` and the entry status, and stamps the run.")
    return "\n".join(lines) + "\n"


def find_open_issue(title, run=subprocess.run):
    completed = run(
        ["gh", "issue", "list", "--state", "open", "--search", f'"{title}" in:title', "--json", "number,title"],
        capture_output=True, text=True, check=True,
    )
    for issue in json.loads(completed.stdout or "[]"):
        if issue["title"] == title:
            return issue["number"]
    return None


def publish_report(title, report, run=subprocess.run):
    number = find_open_issue(title, run)
    if number is None:
        run(["gh", "issue", "create", "--title", title, "--body", report], check=True)
        return "created", None
    run(["gh", "issue", "comment", str(number), "--body", report], check=True)
    return "commented", number


def watch(root, tag, images, results_dir, runner=run_repro.run_entry, resolver=resolve_digest.resolve, github_token=None):
    if tag in images["tags"]:
        return None
    baselines = entry_baselines(root, list(images["tags"]))
    if not baselines:
        return {"tag": tag, "digest": None, "rows": []}
    resolved = resolver(images["image"], [tag], github_token=github_token)
    candidate = {"image": images["image"], "tags": dict(images["tags"], **resolved)}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
        json.dump(candidate, handle)
        candidate_path = handle.name
    try:
        rows = run_all(root, tag, candidate_path, baselines, results_dir, runner)
    finally:
        os.unlink(candidate_path)
    return {"tag": tag, "digest": resolved[tag]["digest"], "rows": rows}


def build_parser():
    parser = argparse.ArgumentParser(description="Run every entry against the newest upstream release.")
    parser.add_argument("--tag")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--report", default="watch-report.md")
    parser.add_argument("--open-issue", action="store_true")
    return parser


def main(argv=None, env=None, runner=run_repro.run_entry, resolver=resolve_digest.resolve, latest=latest_release, publish=publish_report):
    args = build_parser().parse_args(argv)
    env = os.environ if env is None else env
    token = env.get("GITHUB_TOKEN") or env.get("GH_TOKEN")
    try:
        images = json.loads((Path(args.root) / "harness" / "images.json").read_text(encoding="utf-8"))
        tag = args.tag or latest(token=token)
        if not tag:
            print("the latest upstream release is a prerelease or canary; nothing to do")
            return 0
        outcome = watch(args.root, tag, images, args.results_dir, runner, resolver, token)
    except (WatchError, resolve_digest.ResolveError, OSError, ValueError, KeyError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if outcome is None:
        print(f"{tag} is already pinned; nothing to do")
        return 0
    changed = changed_rows(outcome["rows"])
    if not changed:
        print(f"{tag}: {len(outcome['rows'])} entries ran, every result matched the newest pinned tag")
        return 0
    report = render_report(tag, outcome["digest"], outcome["rows"], run_repro.describe_run_url(env))
    Path(args.report).write_text(report, encoding="utf-8")
    print(report)
    if args.open_issue:
        action, number = publish(issue_title(tag), report)
        print(f"issue {action}{'' if number is None else f' #{number}'}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
