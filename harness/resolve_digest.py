#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parent
DEFAULT_IMAGES = HARNESS_DIR / "images.json"
AUTH_URL = "https://auth.docker.io/token?service=registry.docker.io&scope=repository:{image}:pull"
MANIFEST_URL = "https://registry-1.docker.io/v2/{image}/manifests/{tag}"
RELEASE_URL = "https://api.github.com/repos/{repository}/releases/tags/{tag}"
UPSTREAM_REPOSITORY = "NousResearch/hermes-agent"
INDEX_MEDIA_TYPES = (
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
)
REQUIRED_PLATFORM = ("linux", "amd64")
TIMEOUT_SECONDS = 30


class ResolveError(Exception):
    pass


def http_get(url, headers):
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, {k.lower(): v for k, v in response.headers.items()}, response.read()
    except urllib.error.HTTPError as error:
        return error.code, {k.lower(): v for k, v in error.headers.items()}, error.read()


def read_json_body(status, body, what):
    if status != 200:
        raise ResolveError(f"{what} answered HTTP {status}")
    try:
        return json.loads(body)
    except ValueError:
        raise ResolveError(f"{what} did not answer JSON") from None


def registry_token(image, fetch=http_get):
    status, _, body = fetch(AUTH_URL.format(image=image), {})
    token = read_json_body(status, body, "the registry token endpoint").get("token")
    if not token:
        raise ResolveError("the registry token endpoint returned no token")
    return token


def platforms_of(index):
    return sorted(
        (entry.get("platform", {}).get("os"), entry.get("platform", {}).get("architecture"))
        for entry in index.get("manifests", [])
    )


def index_digest(image, tag, token, fetch=http_get):
    headers = {"Authorization": f"Bearer {token}", "Accept": ", ".join(INDEX_MEDIA_TYPES)}
    status, response_headers, body = fetch(MANIFEST_URL.format(image=image, tag=tag), headers)
    index = read_json_body(status, body, f"the manifest of {image}:{tag}")
    media_type = response_headers.get("content-type", "").split(";")[0].strip()
    if media_type not in INDEX_MEDIA_TYPES:
        raise ResolveError(f"{image}:{tag} is not a multi-platform index ({media_type or 'no content type'})")
    computed = "sha256:" + hashlib.sha256(body).hexdigest()
    announced = response_headers.get("docker-content-digest")
    if announced and announced != computed:
        raise ResolveError(f"{image}:{tag} digest header {announced} does not match the body {computed}")
    if REQUIRED_PLATFORM not in platforms_of(index):
        raise ResolveError(f"{image}:{tag} has no {'/'.join(REQUIRED_PLATFORM)} image")
    return computed


def release_date(tag, fetch=http_get, token=None):
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    status, _, body = fetch(RELEASE_URL.format(repository=UPSTREAM_REPOSITORY, tag=tag), headers)
    published = read_json_body(status, body, f"the upstream release {tag}").get("published_at")
    if not published:
        raise ResolveError(f"the upstream release {tag} has no publication date")
    return published[:10]


def resolve(image, tags, fetch=http_get, github_token=None):
    token = registry_token(image, fetch)
    return {
        tag: {
            "digest": index_digest(image, tag, token, fetch),
            "published": release_date(tag, fetch, github_token),
        }
        for tag in tags
    }


def load_images(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_images(path, images):
    Path(path).write_text(json.dumps(images, indent=2) + "\n", encoding="utf-8")


def drift(pinned, resolved):
    return [
        f"{tag}: pinned {pinned[tag]['digest']}, registry {record['digest']}"
        for tag, record in resolved.items()
        if tag in pinned and pinned[tag]["digest"] != record["digest"]
    ]


def build_parser():
    parser = argparse.ArgumentParser(description="Resolve Hermes image tags to registry index digests.")
    parser.add_argument("tags", nargs="*")
    parser.add_argument("--images", default=str(DEFAULT_IMAGES))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--add", action="store_true")
    mode.add_argument("--check", action="store_true")
    return parser


def main(argv=None, fetch=http_get, env=None):
    args = build_parser().parse_args(argv)
    env = os.environ if env is None else env
    try:
        images = load_images(args.images)
        tags = args.tags or list(images["tags"])
        resolved = resolve(images["image"], tags, fetch, env.get("GITHUB_TOKEN"))
    except (ResolveError, OSError, ValueError, KeyError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if args.check:
        problems = drift(images["tags"], resolved)
        for problem in problems:
            print(problem, file=sys.stderr)
        return 1 if problems else 0
    if args.add:
        images["tags"].update(resolved)
        write_images(args.images, images)
    print(json.dumps(resolved, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
