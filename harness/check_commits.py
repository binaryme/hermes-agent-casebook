#!/usr/bin/env python3
import argparse
import re
import subprocess
import sys

TYPES = ("feat", "fix", "docs", "chore", "ci", "test", "refactor", "perf", "build", "style", "revert")
HEADER_PATTERN = re.compile(r"^(?:" + "|".join(TYPES) + r")(?:\([a-z0-9-]+\))?!?: \S.*$")
MAX_HEADER_LENGTH = 100
TRAILER_PATTERN = re.compile(r"^([A-Za-z][A-Za-z0-9-]*): .+$")
ALLOWED_TRAILERS = {"signed-off-by"}
FORBIDDEN_TEXT = re.compile(r"^\s*co-authored-by:|^\W*generated with\b", re.IGNORECASE | re.MULTILINE)
RECORD_SEPARATOR = "\x1e"
FIELD_SEPARATOR = "\x1f"


def message_problems(message):
    lines = message.rstrip("\n").split("\n")
    header = lines[0]
    problems = []
    if not HEADER_PATTERN.match(header):
        problems.append(f"header is not a Conventional Commits header: {header!r}")
    if len(header) > MAX_HEADER_LENGTH:
        problems.append(f"header is longer than {MAX_HEADER_LENGTH} characters")
    if len(lines) > 1 and lines[1].strip():
        problems.append("the header must be followed by a blank line")
    body_lines = [line for line in lines[2:] if line.strip()]
    if not body_lines:
        problems.append("the body is empty; say why the change was made")
    paragraphs = "\n".join(lines[2:]).strip().split("\n\n")
    last = paragraphs[-1].split("\n") if paragraphs and paragraphs[-1] else []
    if last and all(TRAILER_PATTERN.match(line) for line in last):
        for line in last:
            name = TRAILER_PATTERN.match(line).group(1)
            if name.lower() not in ALLOWED_TRAILERS:
                problems.append(f"trailer {name!r} is not allowed; only Signed-off-by is")
    if FORBIDDEN_TEXT.search(message):
        problems.append("the message names a co-author or a generator; disclose AI use in the README instead")
    return problems


def read_commits(revision_range, run=subprocess.run):
    completed = run(
        ["git", "log", "--no-merges", f"--format=%H{FIELD_SEPARATOR}%B{RECORD_SEPARATOR}", revision_range],
        capture_output=True, text=True, check=True,
    )
    commits = []
    for record in completed.stdout.split(RECORD_SEPARATOR):
        record = record.strip("\n")
        if not record:
            continue
        sha, _, message = record.partition(FIELD_SEPARATOR)
        commits.append((sha, message))
    return commits


def build_parser():
    parser = argparse.ArgumentParser(description="Check commit messages: header, body and trailers.")
    parser.add_argument("revision_range", nargs="?", default="HEAD")
    return parser


def main(argv=None, run=subprocess.run):
    args = build_parser().parse_args(argv)
    try:
        commits = read_commits(args.revision_range, run)
    except subprocess.CalledProcessError as error:
        print(f"error: git log failed: {error.stderr or error}", file=sys.stderr)
        return 2
    failed = 0
    for sha, message in commits:
        for problem in message_problems(message):
            print(f"{sha[:12]}: {problem}")
            failed = 1
    if not failed:
        print(f"{len(commits)} commits checked")
    return failed


if __name__ == "__main__":
    sys.exit(main())
