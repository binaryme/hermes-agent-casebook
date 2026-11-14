import hashlib
import hmac
import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

HARNESS = Path(__file__).resolve().parent.parent / "harness"

FAKE_CURL = """#!/usr/bin/env bash
printf '%s\\n' "$@" > "$FAKE_CURL_ARGS"
for arg in "$@"; do
    case "$arg" in
        @*) cp "${arg#@}" "$FAKE_CURL_BODY" ;;
    esac
done
printf '202'
"""

SECRET = "placeholder-secret"


def mac(data):
    return hmac.new(SECRET.encode(), data, hashlib.sha256).hexdigest()


class GatewayShellCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        bin_dir = root / "bin"
        bin_dir.mkdir()
        curl = bin_dir / "curl"
        curl.write_text(FAKE_CURL, encoding="utf-8")
        curl.chmod(0o755)
        self.work = root / "work"
        self.work.mkdir()
        self.args_file = root / "curl-args.txt"
        self.body_file = root / "curl-body.bin"
        self.payload = root / "payload.json"
        self.payload.write_bytes(b'{"event":"message_created"}')
        self.env = {
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "FAKE_CURL_ARGS": str(self.args_file),
            "FAKE_CURL_BODY": str(self.body_file),
            "HARNESS": str(HARNESS),
            "WORK": str(self.work),
            "HERMES_IMAGE": "example/hermes@sha256:abc",
            "GATEWAY_URL": "http://127.0.0.1:9",
        }

    def call(self, snippet):
        return subprocess.run(
            ["bash", "-c", f'source "{HARNESS}/lib.sh"; source "{HARNESS}/gateway.sh"; {snippet}'],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def sent_headers(self):
        args = self.args_file.read_text(encoding="utf-8").splitlines()
        headers = {}
        for flag, value in zip(args, args[1:]):
            if flag == "-H":
                name, _, content = value.partition(": ")
                headers[name] = content
        return headers, args


class PostTests(GatewayShellCase):
    def test_post_v2_signs_timestamp_and_body(self):
        completed = self.call(f'post_v2 route-a "{self.payload}" {SECRET}')
        self.assertEqual(completed.stdout, "202", completed.stderr)
        headers, args = self.sent_headers()
        stamp = headers["X-Webhook-Timestamp"]
        self.assertEqual(headers["X-Webhook-Signature-V2"], mac(stamp.encode() + b"." + self.payload.read_bytes()))
        self.assertIn("http://127.0.0.1:9/webhooks/route-a", args)

    def test_post_github_sets_event_and_delivery(self):
        self.call(f'post_github route-b "{self.payload}" {SECRET} delivery-7 pull_request')
        headers, _ = self.sent_headers()
        self.assertEqual(headers["X-GitHub-Event"], "pull_request")
        self.assertEqual(headers["X-GitHub-Delivery"], "delivery-7")
        self.assertEqual(headers["X-Hub-Signature-256"], "sha256=" + mac(self.payload.read_bytes()))

    def test_post_github_defaults_to_push(self):
        self.call(f'post_github route-b "{self.payload}" {SECRET} delivery-8')
        self.assertEqual(self.sent_headers()[0]["X-GitHub-Event"], "push")

    def test_chatwoot_raw_sends_chatwoot_header_names(self):
        self.call(f'post_chatwoot route-c "{self.payload}" {SECRET} raw')
        headers, _ = self.sent_headers()
        self.assertTrue(headers["X-Chatwoot-Signature"].startswith("sha256="))
        self.assertNotIn("X-Webhook-Signature-V2", headers)

    def test_chatwoot_mapped_sends_v2_header_names_with_the_same_mac(self):
        self.call(f'post_chatwoot route-c "{self.payload}" {SECRET} mapped')
        headers, _ = self.sent_headers()
        stamp = headers["X-Webhook-Timestamp"]
        self.assertEqual(headers["X-Webhook-Signature-V2"], mac(stamp.encode() + b"." + self.payload.read_bytes()))
        self.assertIn("X-Request-ID", headers)

    def test_chatwoot_tampered_sends_a_body_the_signature_does_not_cover(self):
        self.call(f'post_chatwoot route-c "{self.payload}" {SECRET} tampered')
        headers, _ = self.sent_headers()
        stamp = headers["X-Webhook-Timestamp"]
        sent = self.body_file.read_bytes()
        self.assertNotEqual(sent, self.payload.read_bytes())
        self.assertEqual(headers["X-Webhook-Signature-V2"], mac(stamp.encode() + b"." + self.payload.read_bytes()))

    def test_chatwoot_stale_is_outside_the_replay_window(self):
        self.call(f'post_chatwoot route-c "{self.payload}" {SECRET} stale')
        headers, _ = self.sent_headers()
        self.assertGreater(time.time() - int(headers["X-Webhook-Timestamp"]), 300)

    def test_unknown_chatwoot_mode_fails(self):
        completed = self.call(f'post_chatwoot route-c "{self.payload}" {SECRET} bogus')
        self.assertEqual(completed.returncode, 2)


class ConfigTests(GatewayShellCase):
    def test_appends_the_stub_model_block(self):
        data = self.work / "data"
        data.mkdir()
        (data / "config.yaml").write_text("platforms:\n  webhook:\n    enabled: true\n")
        completed = self.call(f'STUB_PORT=4321; write_stub_model_config "{data}"')
        self.assertEqual(completed.returncode, 0, completed.stderr)
        text = (data / "config.yaml").read_text()
        self.assertIn("base_url: http://host.docker.internal:4321/v1", text)
        self.assertIn("provider: custom", text)
        self.assertIn("journal_mode: delete", text)

    def test_refuses_a_fixture_that_sets_its_own_model(self):
        data = self.work / "data"
        data.mkdir()
        (data / "config.yaml").write_text("model:\n  default: other\n")
        completed = self.call(f'STUB_PORT=4321; write_stub_model_config "{data}"')
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("must not set model", completed.stderr)


class StubLogTests(GatewayShellCase):
    def write_log(self, count):
        log = self.work / "stub.jsonl"
        record = {"method": "POST", "path": "/v1/chat/completions", "body": {"messages": [{"role": "user", "content": "MARK"}]}}
        log.write_text("".join(json.dumps(record) + "\n" for _ in range(count)))
        return log

    def test_stub_wait_returns_once_enough_requests_arrived(self):
        log = self.write_log(2)
        completed = self.call(f'STUB_LOG="{log}"; stub_wait 2 3')
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_stub_wait_times_out(self):
        log = self.write_log(0)
        completed = self.call(f'STUB_LOG="{log}"; stub_wait 1 1')
        self.assertEqual(completed.returncode, 1)

    def test_stub_text_prints_message_contents(self):
        log = self.write_log(1)
        completed = self.call(f'STUB_LOG="{log}"; stub_text 0')
        self.assertEqual(completed.stdout.strip(), "MARK")


class DownTests(GatewayShellCase):
    def test_gateway_down_is_idempotent_without_a_gateway(self):
        completed = self.call("gateway_down; gateway_down; echo done")
        self.assertEqual(completed.stdout.strip(), "done")


if __name__ == "__main__":
    unittest.main()
