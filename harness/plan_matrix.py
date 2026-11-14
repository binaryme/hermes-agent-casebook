#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness import run_repro

ROOT = run_repro.ROOT

SHARED_PREFIXES = ("harness/", ".github/workflows/")
GUIDE_PREFIX = "guides/chatwoot/"
ENTRIES_PREFIX = "entries/"


class PlanError(Exception):
    pass


def changed_paths_from_diff(output):
    return [path for path in output.split("\0") if path]


def selects_every_entry(path):
    if path.startswith(SHARED_PREFIXES):
        return True
    return path.startswith(GUIDE_PREFIX) and not path.endswith(".md")


def entry_slug_of(path):
    if not path.startswith(ENTRIES_PREFIX):
        return None
    parts = path[len(ENTRIES_PREFIX):].split("/")
    if len(parts) < 2:
        return None
    return parts[0]


def selected_slugs(paths, expectations):
    if any(selects_every_entry(path) for path in paths):
        return set(expectations)
    changed = {entry_slug_of(path) for path in paths}
    return {slug for slug in changed if slug in expectations}


def order_tags(tags, tag_order):
    position = {tag: index for index, tag in enumerate(tag_order)}
    return sorted(tags, key=lambda tag: (position.get(tag, len(position)), tag))


def build_matrix(slugs, expectations, tag_order=(), entry_filter=None, tag_filter=None):
    entries_by_tag = {}
    for slug in sorted(slugs):
        if entry_filter and slug != entry_filter:
            continue
        for tag in expectations[slug]:
            if tag_filter and tag != tag_filter:
                continue
            entries_by_tag.setdefault(tag, []).append(slug)
    return {
        "include": [
            {"tag": tag, "entries": entries_by_tag[tag]}
            for tag in order_tags(entries_by_tag, tag_order)
        ]
    }


def plan_from_paths(paths, expectations, tag_order=()):
    return build_matrix(selected_slugs(paths, expectations), expectations, tag_order)


def plan_everything(expectations, tag_order=(), entry_filter=None, tag_filter=None):
    if entry_filter and entry_filter not in expectations:
        raise PlanError(f"no entry named {entry_filter}")
    matrix = build_matrix(set(expectations), expectations, tag_order, entry_filter, tag_filter)
    if (entry_filter or tag_filter) and not matrix["include"]:
        raise PlanError("the entry and tag filters select nothing")
    return matrix


def format_github_output(matrix):
    return (
        f"matrix={json.dumps(matrix, separators=(',', ':'))}\n"
        f"has_work={'true' if matrix['include'] else 'false'}\n"
    )


def load_expectations(root):
    expectations = {}
    entries_dir = Path(root) / "entries"
    if not entries_dir.is_dir():
        return expectations
    for entry_dir in sorted(entries_dir.iterdir()):
        expect_path = entry_dir / "expect.json"
        if not (entry_dir.is_dir() and expect_path.is_file()):
            continue
        if not run_repro.SLUG_PATTERN.match(entry_dir.name):
            continue
        expectations[entry_dir.name] = list(json.loads(expect_path.read_text(encoding="utf-8")))
    return expectations


def load_tag_order(root):
    images_path = Path(root) / "harness" / "images.json"
    if not images_path.is_file():
        return []
    return list(json.loads(images_path.read_text(encoding="utf-8")).get("tags", {}))


def diff_paths(root, base, head, run=subprocess.run):
    completed = run(
        ["git", "diff", "--name-only", "--no-renames", "-z", f"{base}...{head}"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return changed_paths_from_diff(completed.stdout)


def build_parser():
    parser = argparse.ArgumentParser(description="Plan which entries run on which tags.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--paths", nargs="*")
    source.add_argument("--base")
    source.add_argument("--all", action="store_true")
    parser.add_argument("--head")
    parser.add_argument("--entry", default="")
    parser.add_argument("--tag", default="")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--github-output", action="store_true")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.base and not args.head:
        print("--base needs --head", file=sys.stderr)
        return 2
    expectations = load_expectations(args.root)
    tag_order = load_tag_order(args.root)
    try:
        if args.all:
            matrix = plan_everything(expectations, tag_order, args.entry or None, args.tag or None)
        else:
            paths = args.paths if args.paths is not None else diff_paths(args.root, args.base, args.head)
            matrix = plan_from_paths(paths, expectations, tag_order)
    except (PlanError, subprocess.CalledProcessError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(json.dumps(matrix))
    if args.github_output:
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as handle:
            handle.write(format_github_output(matrix))
    return 0


if __name__ == "__main__":
    sys.exit(main())
