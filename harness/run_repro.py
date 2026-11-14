#!/usr/bin/env python3
import argparse
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parent
ROOT = HARNESS_DIR.parent

OBSERVED_PREFIX = "OBSERVED="
MATCH = "match"
BEHAVIOR_CHANGED = "behavior-changed"
REPRO_ERROR = "repro-error"
DEFAULT_TIMEOUT = 300
TERMINATE_GRACE_SECONDS = 10

SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
TAG_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
TOKEN_PATTERN = re.compile(r"^\S+$")


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Execution:
    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool
    duration_s: float


@dataclass(frozen=True)
class Verdict:
    token: str | None
    outcome: str
    reason: str | None


def validate_slug(slug):
    if not SLUG_PATTERN.match(slug):
        raise ConfigError(f"invalid entry slug: {slug!r}")
    return slug


def validate_tag(tag):
    if not TAG_PATTERN.match(tag):
        raise ConfigError(f"invalid tag: {tag!r}")
    return tag


def image_reference(images, tag):
    tags = images.get("tags", {})
    if tag not in tags:
        raise ConfigError(f"tag {tag} is not pinned in images.json")
    digest = tags[tag]["digest"]
    return f"{images['image']}@{digest}", digest


def expected_token(expectations, tag, override=None):
    if override is not None:
        return override
    if tag not in expectations:
        raise ConfigError(f"expect.json has no expectation for tag {tag}")
    return expectations[tag]


def build_environment(base_env, image, tag, harness_dir, entry_dir, work_dir):
    env = dict(base_env)
    env.update(
        {
            "HERMES_IMAGE": image,
            "HARNESS": str(harness_dir),
            "ENTRY_DIR": str(entry_dir),
            "FIXTURES": str(Path(entry_dir) / "fixtures"),
            "WORK": str(work_dir),
            "HERMES_TAG": tag,
        }
    )
    return env


def find_observed_lines(stdout):
    return [
        line[len(OBSERVED_PREFIX):].rstrip("\r")
        for line in stdout.splitlines()
        if line.startswith(OBSERVED_PREFIX)
    ]


def evaluate(execution, expected):
    if execution.timed_out:
        return Verdict(None, REPRO_ERROR, "repro timed out")
    if execution.returncode != 0:
        return Verdict(None, REPRO_ERROR, f"repro exited with status {execution.returncode}")
    lines = find_observed_lines(execution.stdout)
    if len(lines) != 1:
        return Verdict(None, REPRO_ERROR, f"expected exactly one OBSERVED line, found {len(lines)}")
    token = lines[0]
    if not TOKEN_PATTERN.match(token):
        return Verdict(None, REPRO_ERROR, f"malformed OBSERVED token: {token!r}")
    outcome = MATCH if token == expected else BEHAVIOR_CHANGED
    return Verdict(token, outcome, None)


def describe_runner(env, system, machine):
    runner_os = env.get("RUNNER_OS") or system
    runner_arch = env.get("RUNNER_ARCH") or machine
    return f"{runner_os}-{runner_arch}"


def describe_run_url(env):
    server = env.get("GITHUB_SERVER_URL")
    repository = env.get("GITHUB_REPOSITORY")
    run_id = env.get("GITHUB_RUN_ID")
    if not (server and repository and run_id):
        return None
    return f"{server}/{repository}/actions/runs/{run_id}"


def format_timestamp(moment):
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_result(slug, tag, digest, verdict, expected, execution, runner, moment, run_url):
    return {
        "slug": slug,
        "tag": tag,
        "digest": digest,
        "token": verdict.token,
        "expected": expected,
        "class": verdict.outcome,
        "duration_s": round(execution.duration_s, 3),
        "runner": runner,
        "timestamp_utc": format_timestamp(moment),
        "run_url": run_url,
    }


def result_path(results_dir, slug, tag):
    return Path(results_dir) / slug / f"{tag}.json"


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"missing file: {path}") from None
    except json.JSONDecodeError as error:
        raise ConfigError(f"invalid JSON in {path}: {error}") from None


def write_result(path, result):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


def terminate_process_group(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=TERMINATE_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return


def execute(script, env, cwd, timeout):
    started = time.monotonic()
    process = subprocess.Popen(
        ["bash", str(script)],
        env=env,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        terminate_process_group(process)
        stdout, stderr = process.communicate()
    return Execution(
        returncode=None if timed_out else process.returncode,
        stdout=stdout or "",
        stderr=stderr or "",
        timed_out=timed_out,
        duration_s=time.monotonic() - started,
    )


def run_entry(
    slug,
    tag,
    root=ROOT,
    images_path=None,
    results_dir="results",
    timeout=DEFAULT_TIMEOUT,
    expect_override=None,
    env=None,
    runner=execute,
    clock=lambda: datetime.now(timezone.utc),
):
    validate_slug(slug)
    validate_tag(tag)
    root = Path(root)
    harness_dir = root / "harness"
    entry_dir = root / "entries" / slug
    script = entry_dir / "repro.sh"
    if not script.is_file():
        raise ConfigError(f"missing repro: {script}")
    images = read_json(images_path or harness_dir / "images.json")
    image, digest = image_reference(images, tag)
    expected = expected_token(read_json(entry_dir / "expect.json"), tag, expect_override)
    base_env = dict(os.environ if env is None else env)
    work_dir = Path(tempfile.mkdtemp(prefix=f"casebook-{slug}-"))
    try:
        run_env = build_environment(base_env, image, tag, harness_dir, entry_dir, work_dir)
        execution = runner(script, run_env, work_dir, timeout)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
    verdict = evaluate(execution, expected)
    result = build_result(
        slug,
        tag,
        digest,
        verdict,
        expected,
        execution,
        describe_runner(base_env, platform.system(), platform.machine()),
        clock(),
        describe_run_url(base_env),
    )
    write_result(result_path(results_dir, slug, tag), result)
    return result, verdict, execution


def report(result, verdict, execution, stream):
    print(
        f"{result['slug']} {result['tag']}: {result['class']}"
        f" (token={result['token']} expected={result['expected']})",
        file=stream,
    )
    if verdict.reason:
        print(f"  reason: {verdict.reason}", file=stream)
    if verdict.outcome == REPRO_ERROR and execution.stderr.strip():
        tail = execution.stderr.strip().splitlines()[-20:]
        print("  stderr tail:", file=stream)
        for line in tail:
            print(f"    {line}", file=stream)


def tags_in_expectations(root, slug):
    return list(read_json(Path(root) / "entries" / validate_slug(slug) / "expect.json"))


def build_parser():
    parser = argparse.ArgumentParser(description="Run one entry repro against one pinned image.")
    parser.add_argument("--entry", required=True)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--tag")
    target.add_argument("--all-tags", action="store_true")
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--images")
    parser.add_argument("--expect")
    return parser


def main(argv=None, root=ROOT, env=None, runner=execute):
    args = build_parser().parse_args(argv)
    if args.all_tags and args.expect is not None:
        print("--expect needs --tag", file=sys.stderr)
        return 2
    try:
        tags = tags_in_expectations(root, args.entry) if args.all_tags else [args.tag]
        matched_all = True
        for tag in tags:
            result, verdict, execution = run_entry(
                args.entry,
                tag,
                root=root,
                images_path=args.images,
                results_dir=args.results_dir,
                timeout=args.timeout,
                expect_override=args.expect,
                env=env,
                runner=runner,
            )
            report(result, verdict, execution, sys.stderr)
            matched_all = matched_all and verdict.outcome == MATCH
    except ConfigError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0 if matched_all else 1


if __name__ == "__main__":
    sys.exit(main())
