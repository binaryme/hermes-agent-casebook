import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from harness import sign

SECRET = "placeholder-secret"
BODY = b'{"event":"message_created","id":1}'
TIMESTAMP = 1700000000
TIMESTAMPED_MAC = "c3eda94978f9a74732339f951be3a6b5149bc88d9fae770e27845eebf7310be5"
BODY_MAC = "a78fd401faf96ef6e357ff0d651267459b0a96a810a57eb1818590a38759b04b"


class V2Tests(unittest.TestCase):
    def test_matches_an_independently_computed_vector(self):
        self.assertEqual(
            sign.v2_headers(SECRET, BODY, TIMESTAMP),
            {"X-Webhook-Timestamp": "1700000000", "X-Webhook-Signature-V2": TIMESTAMPED_MAC},
        )

    def test_defaults_to_the_current_time(self):
        headers = sign.v2_headers(SECRET, BODY)
        self.assertTrue(headers["X-Webhook-Timestamp"].isdigit())
        self.assertEqual(len(headers["X-Webhook-Signature-V2"]), 64)


class GithubTests(unittest.TestCase):
    def test_matches_an_independently_computed_vector(self):
        self.assertEqual(
            sign.github_headers(SECRET, BODY, "delivery-1", "pull_request"),
            {
                "X-Hub-Signature-256": "sha256=" + BODY_MAC,
                "X-GitHub-Event": "pull_request",
                "X-GitHub-Delivery": "delivery-1",
            },
        )


class ChatwootTests(unittest.TestCase):
    def test_uses_the_same_mac_as_v2_with_a_prefix(self):
        headers = sign.chatwoot_headers(SECRET, BODY, TIMESTAMP, "delivery-2")
        self.assertEqual(
            headers,
            {
                "X-Chatwoot-Timestamp": "1700000000",
                "X-Chatwoot-Signature": "sha256=" + TIMESTAMPED_MAC,
                "X-Chatwoot-Delivery": "delivery-2",
            },
        )

    def test_generates_a_delivery_id_when_none_is_given(self):
        self.assertTrue(sign.chatwoot_headers(SECRET, BODY, TIMESTAMP)["X-Chatwoot-Delivery"])

    def test_mapping_produces_valid_v2_headers(self):
        mapped = sign.chatwoot_to_v2(sign.chatwoot_headers(SECRET, BODY, TIMESTAMP, "delivery-3"))
        self.assertEqual(
            mapped,
            {
                "X-Webhook-Timestamp": "1700000000",
                "X-Webhook-Signature-V2": TIMESTAMPED_MAC,
                "X-Request-ID": "delivery-3",
            },
        )
        self.assertEqual(
            {k: v for k, v in mapped.items() if k != "X-Request-ID"},
            sign.v2_headers(SECRET, BODY, TIMESTAMP),
        )

    def test_mapping_is_case_insensitive_and_tolerates_a_bare_signature(self):
        mapped = sign.chatwoot_to_v2({"x-chatwoot-signature": TIMESTAMPED_MAC, "x-chatwoot-timestamp": "5"})
        self.assertEqual(mapped, {"X-Webhook-Timestamp": "5", "X-Webhook-Signature-V2": TIMESTAMPED_MAC})

    def test_mapping_rejects_unsigned_requests(self):
        with self.assertRaises(ValueError):
            sign.chatwoot_to_v2({"X-Chatwoot-Timestamp": "5"})


class CliTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.body = Path(self.directory.name) / "body.json"
        self.body.write_bytes(BODY)

    def run_cli(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = sign.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_prints_header_lines(self):
        code, out, _ = self.run_cli(["v2", SECRET, str(self.body), "--timestamp", str(TIMESTAMP)])
        self.assertEqual(code, 0)
        self.assertEqual(
            out.splitlines(),
            ["X-Webhook-Timestamp: 1700000000", f"X-Webhook-Signature-V2: {TIMESTAMPED_MAC}"],
        )

    def test_chatwoot_mapped_scheme(self):
        code, out, _ = self.run_cli(
            ["chatwoot-mapped", SECRET, str(self.body), "--timestamp", str(TIMESTAMP), "--delivery-id", "d"]
        )
        self.assertEqual(code, 0)
        self.assertIn("X-Request-ID: d", out.splitlines())

    def test_github_requires_a_delivery_id(self):
        code, _, err = self.run_cli(["github", SECRET, str(self.body)])
        self.assertEqual(code, 2)
        self.assertIn("--delivery-id", err)

    def test_missing_body_file_is_an_error(self):
        code, _, _ = self.run_cli(["v2", SECRET, str(Path(self.directory.name) / "missing.json")])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
