import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from harness import resolve_digest

OCI_INDEX = "application/vnd.oci.image.index.v1+json"


def index_body(platforms):
    manifests = [{"platform": {"os": os_name, "architecture": arch}} for os_name, arch in platforms]
    return json.dumps({"manifests": manifests}).encode()


def digest_of(body):
    return "sha256:" + hashlib.sha256(body).hexdigest()


class FakeRegistry:
    def __init__(self, indexes, releases, media_type=OCI_INDEX, digest_override=None):
        self.indexes = indexes
        self.releases = releases
        self.media_type = media_type
        self.digest_override = digest_override
        self.requests = []

    def __call__(self, url, headers):
        self.requests.append((url, headers))
        if url.startswith("https://auth.docker.io/"):
            return 200, {}, json.dumps({"token": "registry-token"}).encode()
        if "/manifests/" in url:
            tag = url.rsplit("/", 1)[1]
            if tag not in self.indexes:
                return 404, {}, b"{}"
            body = self.indexes[tag]
            announced = self.digest_override or digest_of(body)
            return 200, {"content-type": self.media_type, "docker-content-digest": announced}, body
        if "/releases/tags/" in url:
            tag = url.rsplit("/", 1)[1]
            if tag not in self.releases:
                return 404, {}, b"{}"
            return 200, {}, json.dumps({"published_at": self.releases[tag]}).encode()
        return 500, {}, b""


AMD64_AND_ARM64 = index_body([("linux", "amd64"), ("linux", "arm64")])


class ResolveTests(unittest.TestCase):
    def test_resolves_digest_and_release_date(self):
        registry = FakeRegistry({"v1.0.0": AMD64_AND_ARM64}, {"v1.0.0": "2026-05-04T10:00:00Z"})
        resolved = resolve_digest.resolve("example/hermes", ["v1.0.0"], registry)
        self.assertEqual(
            resolved,
            {"v1.0.0": {"digest": digest_of(AMD64_AND_ARM64), "published": "2026-05-04"}},
        )

    def test_sends_bearer_token_and_index_accept_header(self):
        registry = FakeRegistry({"v1.0.0": AMD64_AND_ARM64}, {"v1.0.0": "2026-05-04T10:00:00Z"})
        resolve_digest.resolve("example/hermes", ["v1.0.0"], registry)
        manifest_headers = next(h for url, h in registry.requests if "/manifests/" in url)
        self.assertEqual(manifest_headers["Authorization"], "Bearer registry-token")
        self.assertIn(OCI_INDEX, manifest_headers["Accept"])

    def test_passes_github_token_to_the_release_lookup(self):
        registry = FakeRegistry({"v1.0.0": AMD64_AND_ARM64}, {"v1.0.0": "2026-05-04T10:00:00Z"})
        resolve_digest.resolve("example/hermes", ["v1.0.0"], registry, github_token="gh-placeholder")
        release_headers = next(h for url, h in registry.requests if "/releases/" in url)
        self.assertEqual(release_headers["Authorization"], "Bearer gh-placeholder")

    def test_rejects_a_single_platform_manifest(self):
        registry = FakeRegistry(
            {"v1.0.0": AMD64_AND_ARM64},
            {"v1.0.0": "2026-05-04T10:00:00Z"},
            media_type="application/vnd.oci.image.manifest.v1+json",
        )
        with self.assertRaisesRegex(resolve_digest.ResolveError, "not a multi-platform index"):
            resolve_digest.resolve("example/hermes", ["v1.0.0"], registry)

    def test_rejects_an_index_without_linux_amd64(self):
        arm_only = index_body([("linux", "arm64")])
        registry = FakeRegistry({"v1.0.0": arm_only}, {"v1.0.0": "2026-05-04T10:00:00Z"})
        with self.assertRaisesRegex(resolve_digest.ResolveError, "no linux/amd64"):
            resolve_digest.resolve("example/hermes", ["v1.0.0"], registry)

    def test_rejects_a_digest_header_that_does_not_match_the_body(self):
        registry = FakeRegistry(
            {"v1.0.0": AMD64_AND_ARM64},
            {"v1.0.0": "2026-05-04T10:00:00Z"},
            digest_override="sha256:" + "0" * 64,
        )
        with self.assertRaisesRegex(resolve_digest.ResolveError, "does not match the body"):
            resolve_digest.resolve("example/hermes", ["v1.0.0"], registry)

    def test_unknown_tag_is_an_error(self):
        registry = FakeRegistry({}, {})
        with self.assertRaisesRegex(resolve_digest.ResolveError, "HTTP 404"):
            resolve_digest.resolve("example/hermes", ["v9.9.9"], registry)

    def test_missing_release_is_an_error(self):
        registry = FakeRegistry({"v1.0.0": AMD64_AND_ARM64}, {})
        with self.assertRaisesRegex(resolve_digest.ResolveError, "upstream release v1.0.0"):
            resolve_digest.resolve("example/hermes", ["v1.0.0"], registry)


class DriftTests(unittest.TestCase):
    def test_reports_only_changed_digests(self):
        pinned = {"a": {"digest": "sha256:1"}, "b": {"digest": "sha256:2"}}
        resolved = {"a": {"digest": "sha256:1"}, "b": {"digest": "sha256:3"}}
        self.assertEqual(resolve_digest.drift(pinned, resolved), ["b: pinned sha256:2, registry sha256:3"])


class MainTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.images = Path(self.directory.name) / "images.json"

    def write_images(self, tags):
        self.images.write_text(json.dumps({"image": "example/hermes", "tags": tags}))

    def run_main(self, argv, registry):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = resolve_digest.main(argv + ["--images", str(self.images)], fetch=registry, env={})
        return code, out.getvalue(), err.getvalue()

    def test_add_appends_resolved_tags_in_order(self):
        self.write_images({"v1.0.0": {"digest": digest_of(AMD64_AND_ARM64), "published": "2026-05-04"}})
        newer = index_body([("linux", "amd64")])
        registry = FakeRegistry({"v1.1.0": newer}, {"v1.1.0": "2026-06-01T00:00:00Z"})
        code, _, _ = self.run_main(["--add", "v1.1.0"], registry)
        self.assertEqual(code, 0)
        written = json.loads(self.images.read_text())
        self.assertEqual(list(written["tags"]), ["v1.0.0", "v1.1.0"])
        self.assertEqual(written["tags"]["v1.1.0"]["digest"], digest_of(newer))

    def test_check_passes_when_pins_match(self):
        self.write_images({"v1.0.0": {"digest": digest_of(AMD64_AND_ARM64), "published": "2026-05-04"}})
        registry = FakeRegistry({"v1.0.0": AMD64_AND_ARM64}, {"v1.0.0": "2026-05-04T10:00:00Z"})
        code, _, _ = self.run_main(["--check"], registry)
        self.assertEqual(code, 0)

    def test_check_fails_when_a_tag_was_repushed(self):
        self.write_images({"v1.0.0": {"digest": "sha256:" + "1" * 64, "published": "2026-05-04"}})
        registry = FakeRegistry({"v1.0.0": AMD64_AND_ARM64}, {"v1.0.0": "2026-05-04T10:00:00Z"})
        code, _, err = self.run_main(["--check"], registry)
        self.assertEqual(code, 1)
        self.assertIn("v1.0.0: pinned", err)

    def test_registry_failure_exits_two_and_leaves_the_file_alone(self):
        self.write_images({})
        before = self.images.read_text()
        code, _, err = self.run_main(["--add", "v9.9.9"], FakeRegistry({}, {}))
        self.assertEqual(code, 2)
        self.assertIn("error:", err)
        self.assertEqual(self.images.read_text(), before)


if __name__ == "__main__":
    unittest.main()
