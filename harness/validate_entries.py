import argparse
import datetime
import io
import json
import os
import re
import sys
import tokenize
from dataclasses import dataclass, field
from pathlib import Path

import yaml

REQUIRED_FIELDS = (
    "id",
    "slug",
    "title",
    "kind",
    "status",
    "affected",
    "not_affected",
    "fixed_in",
    "upstream",
    "evidence",
    "repro",
    "needs_credentials",
    "confidence",
    "verified_on",
    "last_reviewed",
    "limits",
    "credits",
)
OPTIONAL_FIELDS = ("searched_on",)
ENUM_FIELDS = {
    "kind": ("gotcha", "check-your-version", "pointer"),
    "status": ("open", "fixed", "documented", "wont-fix", "unreported"),
    "confidence": ("reproduced", "source-verified"),
}
EXPECTED_HEADINGS = (
    "Symptom",
    "Verified on",
    "Reproduce",
    "Expected vs actual",
    "Cause",
    "Workaround",
    "Upstream status",
    "Confidence and limits",
)
NONE_FOUND = "none-found"
SHEBANG = "#!/usr/bin/env bash"
SCANNED_SUFFIXES = (".sh", ".py", ".yml", ".yaml", ".toml")
PRUNED_DIRECTORIES = frozenset(
    {".git", ".venv", "venv", "node_modules", "__pycache__", ".tox", ".mypy_cache", ".pytest_cache"}
)
ABBREVIATIONS = ("e.g.", "i.e.", "vs.", "etc.", "cf.")
EXECUTABLE_BITS = 0o111
MAX_REPRO_LINES = 30
MAX_LIMITS_SENTENCES = 2
MAX_TOKEN_LENGTH = 40
STALE_REVIEW_DAYS = 60

ID_PATTERN = re.compile(r"E[0-9]+")
KEBAB_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
DATE_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
DIGEST_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")
URL_PATTERN = re.compile(r"https://\S+")
DOCKER_TAG_PATTERN = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}")
PINNED_BLOB_PATTERN = re.compile(r"/blob/[0-9a-f]{40}/")
MOVING_REF_PATTERN = re.compile(r"/(?:blob|tree)/(?:main|master|HEAD)(?:/|$)")
TAG_SHAPED_PATTERN = re.compile(r"\bv[0-9]+\.[0-9]+\.[0-9]+\b")
HEADING_PATTERN = re.compile(r"^## +(.+?)\s*$")

ENTRY_RULES = (
    "front-matter",
    "missing-field",
    "unknown-field",
    "field-type",
    "enum",
    "slug",
    "upstream",
    "date-format",
    "evidence-pin",
    "needs-credentials",
    "limits",
    "tag-overlap",
    "fixed-in",
    "verified-on",
    "reproduced-needs-verified-on",
    "pointer-reproduced",
    "repro-path",
    "repro-missing",
    "repro-not-executable",
    "repro-shebang",
    "repro-length",
    "repro-image-tag",
    "expect-missing",
    "expect-invalid",
    "expect-tags",
    "headings",
    "comment-line",
)
REPOSITORY_RULES = ("readme-missing", "duplicate-id", "images-missing", "images-invalid")


@dataclass(frozen=True)
class Finding:
    path: str
    rule: str
    message: str

    def line(self):
        return f"{self.path}: {self.rule}: {self.message}"


@dataclass
class Report:
    violations: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    def violation(self, path, rule, message):
        self.violations.append(Finding(str(path), rule, message))

    def warn(self, path, rule, message):
        self.warnings.append(Finding(str(path), rule, message))

    def extend(self, other):
        self.violations.extend(other.violations)
        self.warnings.extend(other.warnings)


@dataclass(frozen=True)
class Context:
    pinned_tags: frozenset
    today: datetime.date


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def construct_unique_mapping(loader, node, deep=False):
    seen = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            raise yaml.constructor.ConstructorError(
                None, None, f"duplicate key {key!r}", key_node.start_mark
            )
        seen.add(key)
    return yaml.SafeLoader.construct_mapping(loader, node, deep)


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_unique_mapping
)


def non_empty_str(value):
    return isinstance(value, str) and value.strip() != ""


def as_date(value):
    if isinstance(value, datetime.datetime):
        return None
    if isinstance(value, datetime.date):
        return value
    if not (isinstance(value, str) and DATE_PATTERN.fullmatch(value)):
        return None
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        return None


def count_sentences(text):
    flattened = " ".join(text.split())
    for abbreviation in ABBREVIATIONS:
        flattened = flattened.replace(abbreviation, abbreviation.replace(".", ""))
    return len([part for part in re.split(r"(?<=[.!?])\s+", flattened) if part])


def split_front_matter(text):
    lines = text.splitlines()
    if not lines or lines[0].rstrip() != "---":
        return None, text
    for index in range(1, len(lines)):
        if lines[index].rstrip() == "---":
            return "\n".join(lines[1:index]), "\n".join(lines[index + 1 :])
    return None, text


def body_headings(body):
    headings = []
    in_fence = False
    for line in body.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
            continue
        match = None if in_fence else HEADING_PATTERN.match(line)
        if match:
            headings.append(match.group(1))
    return headings


def literal_tags(line, pinned_tags):
    found = set(TAG_SHAPED_PATTERN.findall(line))
    for tag in pinned_tags:
        if re.search(rf"(?<![\w.]){re.escape(tag)}(?![\w.])", line):
            found.add(tag)
    return found


def read_entry(readme, report):
    try:
        text = readme.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        report.violation(readme, "front-matter", f"cannot read file: {error}")
        return None
    raw, body = split_front_matter(text)
    if raw is None:
        report.violation(readme, "front-matter", "file must start with a --- delimited YAML block")
        return None
    try:
        data = yaml.load(raw, Loader=UniqueKeyLoader)
    except yaml.YAMLError as error:
        report.violation(readme, "front-matter", f"invalid YAML: {' '.join(str(error).split())}")
        return None
    if not isinstance(data, dict):
        report.violation(readme, "front-matter", "front matter must be a YAML mapping")
        return None
    return data, body


class EntryChecker:
    def __init__(self, entry_dir, context, report):
        self.dir = entry_dir
        self.readme = entry_dir / "README.md"
        self.context = context
        self.report = report
        self.front = {}

    def fail(self, rule, message, path=None):
        self.report.violation(path or self.readme, rule, message)

    def has(self, name):
        return name in self.front

    def run(self):
        loaded = read_entry(self.readme, self.report)
        if loaded is None:
            return None
        self.front, body = loaded
        self.check_field_names()
        self.check_identity()
        self.check_enums()
        self.check_needs_credentials()
        self.check_tags()
        self.check_upstream()
        self.check_dates()
        self.check_evidence()
        self.check_verified_on()
        self.check_credits()
        self.check_limits()
        self.check_confidence()
        self.check_repro()
        self.check_headings(body)
        return self.front

    def check_field_names(self):
        for name in REQUIRED_FIELDS:
            if not self.has(name):
                self.fail("missing-field", f"{name} is required")
        allowed = set(REQUIRED_FIELDS) | set(OPTIONAL_FIELDS)
        for name in sorted(set(self.front) - allowed, key=str):
            self.fail("unknown-field", f"{name} is not part of the entry schema")

    def check_identity(self):
        if self.has("id") and not (
            isinstance(self.front["id"], str) and ID_PATTERN.fullmatch(self.front["id"])
        ):
            self.fail("field-type", "id must be a string like E1")
        if self.has("title") and not non_empty_str(self.front["title"]):
            self.fail("field-type", "title must be a non-empty string")
        if not self.has("slug"):
            return
        if self.front["slug"] != self.dir.name or not KEBAB_PATTERN.fullmatch(self.dir.name):
            self.fail(
                "slug",
                f"slug must equal the lowercase kebab-case directory name {self.dir.name!r}",
            )

    def check_enums(self):
        for name, allowed in ENUM_FIELDS.items():
            if self.has(name) and self.front[name] not in allowed:
                self.fail("enum", f"{name} must be one of: {', '.join(allowed)}")

    def check_needs_credentials(self):
        if self.has("needs_credentials") and self.front["needs_credentials"] is not False:
            self.fail("needs-credentials", "needs_credentials must be false")

    def tag_list(self, name):
        if not self.has(name):
            return None
        value = self.front[name]
        if isinstance(value, list) and all(non_empty_str(tag) for tag in value):
            return value
        self.fail("field-type", f"{name} must be a list of tag strings")
        return None

    def check_tags(self):
        affected = self.tag_list("affected")
        not_affected = self.tag_list("not_affected")
        fixed_in = self.front.get("fixed_in")
        if fixed_in is not None and not non_empty_str(fixed_in):
            self.fail("field-type", "fixed_in must be a tag string or null")
            fixed_in = None
        both = sorted(set(affected or ()) & set(not_affected or ()))
        for tag in both:
            self.fail("tag-overlap", f"{tag} is listed as both affected and not_affected")
        if fixed_in is not None and not_affected is not None and fixed_in not in not_affected:
            self.fail("fixed-in", f"fixed_in {fixed_in} must also appear in not_affected")
        self.warn_unpinned(affected, not_affected, fixed_in)

    def warn_unpinned(self, affected, not_affected, fixed_in):
        if self.context.pinned_tags is None:
            return
        mentioned = set(affected or ()) | set(not_affected or ())
        if fixed_in is not None:
            mentioned.add(fixed_in)
        for tag in sorted(mentioned - self.context.pinned_tags):
            self.report.warn(self.readme, "tag-not-pinned", f"{tag} is not listed in images.json")

    def check_upstream(self):
        if not self.has("upstream"):
            return
        upstream = self.front["upstream"]
        if upstream == NONE_FOUND:
            if not self.has("searched_on"):
                self.fail("upstream", "none-found requires searched_on: YYYY-MM-DD")
            return
        is_url_list = isinstance(upstream, list) and bool(upstream) and all(map(is_https_url, upstream))
        if not is_url_list:
            self.fail("upstream", "upstream must be a non-empty list of https URLs or none-found")

    def check_dates(self):
        for name in ("last_reviewed", "searched_on"):
            if self.has(name) and as_date(self.front[name]) is None:
                self.fail("date-format", f"{name} must be a YYYY-MM-DD date")
        reviewed = as_date(self.front.get("last_reviewed"))
        if reviewed is None:
            return
        age = (self.context.today - reviewed).days
        if age > STALE_REVIEW_DAYS:
            self.report.warn(
                self.readme, "stale-review", f"last_reviewed is {age} days old (limit {STALE_REVIEW_DAYS})"
            )

    def check_evidence(self):
        if not self.has("evidence"):
            return
        evidence = self.front["evidence"]
        if not (isinstance(evidence, list) and evidence and all(isinstance(url, str) for url in evidence)):
            self.fail("field-type", "evidence must be a non-empty list of URLs")
            return
        for url in evidence:
            self.check_evidence_url(url)

    def check_evidence_url(self, url):
        if MOVING_REF_PATTERN.search(url):
            self.fail("evidence-pin", f"{url} points at a moving ref; pin it to a 40-hex commit")
        elif not PINNED_BLOB_PATTERN.search(url):
            self.fail("evidence-pin", f"{url} must contain /blob/<40-hex commit>/")

    def check_verified_on(self):
        if not self.has("verified_on"):
            return
        verified = self.front["verified_on"]
        if not isinstance(verified, list):
            self.fail("field-type", "verified_on must be a list")
            return
        for index, item in enumerate(verified):
            for problem in verified_on_problems(item):
                self.fail("verified-on", f"verified_on[{index}] {problem}")

    def check_credits(self):
        if not self.has("credits"):
            return
        credits = self.front["credits"]
        valid = isinstance(credits, list) and all(
            non_empty_str(item) or isinstance(item, dict) for item in credits
        )
        if not valid:
            self.fail("field-type", "credits must be a list of strings or mappings")

    def check_limits(self):
        if not self.has("limits"):
            return
        limits = self.front["limits"]
        if not non_empty_str(limits):
            self.fail("field-type", "limits must be a non-empty string")
        elif count_sentences(limits) > MAX_LIMITS_SENTENCES:
            self.fail("limits", f"limits must be at most {MAX_LIMITS_SENTENCES} sentences")

    def check_confidence(self):
        verified = self.front.get("verified_on")
        if self.front.get("confidence") == "reproduced" and verified == []:
            self.fail("reproduced-needs-verified-on", "confidence reproduced requires a non-empty verified_on")

    def check_repro(self):
        kind = self.front.get("kind")
        declared = self.front.get("repro")
        repro = self.dir / "repro.sh"
        expected = f"entries/{self.dir.name}/repro.sh"
        if declared is None and kind != "pointer" and self.has("repro"):
            self.fail("repro-path", f"repro is required unless kind is pointer: {expected}")
        if declared is not None and declared != expected:
            self.fail("repro-path", f"repro must be {expected}")
        present = repro.is_file()
        if declared is not None and not present:
            self.fail("repro-missing", f"{repro} does not exist")
        pointer_without_repro = kind == "pointer" and not present
        if pointer_without_repro and self.front.get("confidence") == "reproduced":
            self.fail("pointer-reproduced", "a pointer without a repro cannot claim reproduced")
        if present:
            self.check_repro_file(repro)
        if present or declared is not None:
            self.check_expect(present)

    def check_repro_file(self, repro):
        if not repro.stat().st_mode & EXECUTABLE_BITS:
            self.fail("repro-not-executable", "repro.sh must be executable", repro)
        lines = repro.read_text(encoding="utf-8", errors="replace").splitlines()
        if not lines or lines[0] != SHEBANG:
            self.fail("repro-shebang", f"first line must be {SHEBANG}", repro)
        non_blank = [line for line in lines if line.strip()]
        if len(non_blank) > MAX_REPRO_LINES:
            self.fail(
                "repro-length",
                f"{len(non_blank)} non-blank lines, limit is {MAX_REPRO_LINES}",
                repro,
            )
        self.check_literal_tags(repro, lines)

    def check_literal_tags(self, repro, lines):
        pinned = self.context.pinned_tags or frozenset()
        for number, line in enumerate(lines, 1):
            for tag in sorted(literal_tags(line, pinned)):
                self.fail("repro-image-tag", f"line {number} names the image tag {tag}", repro)

    def check_expect(self, repro_present):
        expect = self.dir / "expect.json"
        if not expect.is_file():
            if repro_present:
                self.fail("expect-missing", "expect.json is required next to repro.sh", expect)
            return
        try:
            data = json.loads(expect.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            self.fail("expect-invalid", f"cannot read JSON: {error}", expect)
            return
        for problem in expect_problems(data):
            self.fail("expect-invalid", problem, expect)
        if isinstance(data, dict) and self.context.pinned_tags is not None:
            for tag in sorted(set(data) - self.context.pinned_tags):
                self.fail("expect-tags", f"{tag} is not listed in images.json", expect)

    def check_headings(self, body):
        found = body_headings(body)
        expected = list(EXPECTED_HEADINGS)
        if found == expected:
            return
        problems = [f"missing heading '## {heading}'" for heading in expected if heading not in found]
        problems += [f"unexpected heading '## {heading}'" for heading in found if heading not in expected]
        if not problems:
            problems.append(f"headings must appear once each, in order; found {found}")
        for problem in problems:
            self.fail("headings", problem)


def is_token(value):
    return isinstance(value, str) and bool(KEBAB_PATTERN.fullmatch(value)) and len(value) <= MAX_TOKEN_LENGTH


def is_https_url(value):
    return isinstance(value, str) and bool(URL_PATTERN.fullmatch(value))


def is_digest(value):
    return isinstance(value, str) and bool(DIGEST_PATTERN.fullmatch(value))


VERIFIED_ON_VALIDATORS = {
    "tag": (non_empty_str, "a non-empty string"),
    "digest": (is_digest, "sha256:<64 hex>"),
    "date": (lambda value: as_date(value) is not None, "YYYY-MM-DD"),
    "observed": (is_token, "a short lowercase kebab token"),
    "run": (is_https_url, "an https URL"),
}


def verified_on_problems(item):
    if not isinstance(item, dict):
        return ["must be a mapping with tag, digest, date, observed and run"]
    problems = [f"is missing {key}" for key in VERIFIED_ON_VALIDATORS if key not in item]
    problems += [f"has unknown key {key}" for key in sorted(set(item) - set(VERIFIED_ON_VALIDATORS), key=str)]
    for key, (is_valid, description) in VERIFIED_ON_VALIDATORS.items():
        if key in item and not is_valid(item[key]):
            problems.append(f"{key} must be {description}")
    return problems


def expect_problems(data):
    if not isinstance(data, dict) or not data:
        return ["expect.json must be a non-empty JSON object of tag to token"]
    problems = []
    for tag, token in data.items():
        if not is_token(token):
            problems.append(f"token for {tag} must be a short lowercase kebab string")
    return problems


def image_record_problems(tag, record):
    if not DOCKER_TAG_PATTERN.fullmatch(tag):
        return [f"{tag} is not a valid image tag"]
    if not isinstance(record, dict) or set(record) != {"digest", "published"}:
        return [f"{tag} must be an object with exactly digest and published"]
    problems = []
    if not is_digest(record["digest"]):
        problems.append(f"{tag} digest must look like sha256:<64 hex>")
    if as_date(record["published"]) is None:
        problems.append(f"{tag} published must be YYYY-MM-DD")
    return problems


def images_problems(data):
    if not isinstance(data, dict) or set(data) != {"image", "tags"}:
        return ["images.json must be an object with exactly the keys image and tags"]
    problems = []
    if not non_empty_str(data["image"]):
        problems.append("image must be a non-empty string")
    if not isinstance(data["tags"], dict):
        return problems + ["tags must be an object"]
    for tag, record in data["tags"].items():
        problems.extend(image_record_problems(tag, record))
    return problems


def load_images(path, report):
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        report.violation(path, "images-invalid", f"cannot read JSON: {error}")
        return None
    problems = images_problems(data)
    for problem in problems:
        report.violation(path, "images-invalid", problem)
    return None if problems else frozenset(data["tags"])


def entry_directories(entries_dir):
    if not entries_dir.is_dir():
        return []
    children = sorted(entries_dir.iterdir())
    return [child for child in children if child.is_dir() and not child.name.startswith(".")]


def check_entry(entry_dir, context, report):
    if not (entry_dir / "README.md").is_file():
        report.violation(entry_dir / "README.md", "readme-missing", "entry directory has no README.md")
        return None
    return EntryChecker(entry_dir, context, report).run()


def check_unique_ids(directories, fronts, report):
    owners = {}
    for directory, front in zip(directories, fronts):
        entry_id = front.get("id") if front else None
        if not isinstance(entry_id, str):
            continue
        if entry_id in owners:
            report.violation(
                directory / "README.md",
                "duplicate-id",
                f"id {entry_id} is already used by {owners[entry_id].name}",
            )
        owners.setdefault(entry_id, directory)


def line_rule_comment_lines(text):
    numbers = []
    for number, line in enumerate(text.splitlines(), 1):
        is_shebang = number == 1 and line.startswith("#!")
        if line.lstrip().startswith("#") and not is_shebang:
            numbers.append(number)
    return numbers


def python_comment_lines(text):
    numbers = []
    try:
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            is_shebang = token.start == (1, 0) and token.string.startswith("#!")
            if token.type == tokenize.COMMENT and not is_shebang:
                numbers.append(token.start[0])
    except (tokenize.TokenError, SyntaxError):
        return line_rule_comment_lines(text)
    return numbers


def comment_line_numbers(path, text):
    if path.suffix == ".py":
        return python_comment_lines(text)
    return line_rule_comment_lines(text)


def is_fixture_directory(parts):
    if parts[:2] == ("tests", "fixtures"):
        return True
    return len(parts) >= 3 and parts[0] == "entries" and parts[2] == "fixtures"


def scanned_files(root):
    found = []
    for directory, subdirectories, names in os.walk(root):
        relative = Path(directory).relative_to(root).parts
        subdirectories[:] = sorted(
            name
            for name in subdirectories
            if name not in PRUNED_DIRECTORIES and not is_fixture_directory(relative + (name,))
        )
        found.extend(Path(directory) / name for name in sorted(names) if name.endswith(SCANNED_SUFFIXES))
    return found


def check_comment_lines(root):
    report = Report()
    root = Path(root)
    for path in scanned_files(root):
        text = path.read_text(encoding="utf-8", errors="replace")
        for number in comment_line_numbers(path, text):
            report.violation(
                path.relative_to(root).as_posix(), "comment-line", f"line {number} is a comment"
            )
    return report


def validate(root, entries_dir, images_path, today):
    report = Report()
    pinned = load_images(images_path, report)
    directories = entry_directories(entries_dir)
    if directories and pinned is None and not images_path.exists():
        report.violation(images_path, "images-missing", "images.json is required when entries exist")
    context = Context(pinned_tags=pinned, today=today)
    fronts = [check_entry(directory, context, report) for directory in directories]
    check_unique_ids(directories, fronts, report)
    report.extend(check_comment_lines(root))
    return report


def parse_arguments(argv):
    parser = argparse.ArgumentParser(description="Validate casebook entries and repository rules.")
    parser.add_argument("--entries-dir", default="entries", type=Path)
    parser.add_argument("--images", default=Path("harness/images.json"), type=Path)
    parser.add_argument("--root", default=Path("."), type=Path)
    return parser.parse_args(argv)


def main(argv=None):
    arguments = parse_arguments(argv)
    report = validate(
        arguments.root, arguments.entries_dir, arguments.images, datetime.date.today()
    )
    for finding in report.violations:
        print(finding.line())
    for finding in report.warnings:
        print(f"warning: {finding.line()}", file=sys.stderr)
    return 1 if report.violations else 0


if __name__ == "__main__":
    sys.exit(main())
