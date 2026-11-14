import hashlib
import hmac
import http.client
import importlib.util
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RELAY_PATH = Path(__file__).resolve().parent.parent / "guides" / "chatwoot" / "relay" / "relay.py"
spec = importlib.util.spec_from_file_location("chatwoot_relay", RELAY_PATH)
relay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(relay)

SECRET = "placeholder-secret"
BODY = '{"event":"message_created","content":"café — hola","id":7}'.encode("utf-8")


def chatwoot_signature(timestamp, body):
    return "sha256=" + hmac.new(SECRET.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()


class RecordingUpstream:
    def __init__(self, status=202, body=b'{"status": "accepted"}'):
        self.requests = []
        upstream = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                return

            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                upstream.requests.append((self.path, {k.lower(): v for k, v in self.headers.items()}, self.rfile.read(length)))
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/webhooks/chatwoot"

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class RelayCase(unittest.TestCase):
    upstream_status = 202

    def setUp(self):
        self.upstream = RecordingUpstream(status=self.upstream_status)
        self.addCleanup(self.upstream.close)
        self.start_relay(self.upstream.url)

    def start_relay(self, upstream_url, max_bytes=relay.DEFAULT_MAX_BODY_BYTES):
        self.relay = relay.build_server("127.0.0.1", 0, upstream_url, max_bytes)
        threading.Thread(target=self.relay.serve_forever, daemon=True).start()
        self.addCleanup(self.relay.server_close)
        self.addCleanup(self.relay.shutdown)

    def post(self, body=BODY, headers=None, path="/anything"):
        connection = http.client.HTTPConnection("127.0.0.1", self.relay.server_address[1], timeout=10)
        connection.request("POST", path, body=body, headers=headers or {})
        response = connection.getresponse()
        result = response.status, response.read()
        connection.close()
        return result

    def signed_headers(self, timestamp="1700000000", body=BODY, delivery="delivery-1"):
        headers = {
            "Content-Type": "application/json",
            "X-Chatwoot-Timestamp": timestamp,
            "X-Chatwoot-Signature": chatwoot_signature(timestamp, body),
        }
        if delivery:
            headers["X-Chatwoot-Delivery"] = delivery
        return headers


class ForwardingTests(RelayCase):
    def test_forwards_the_body_byte_for_byte(self):
        status, _ = self.post(headers=self.signed_headers())
        self.assertEqual(status, 202)
        _, _, body = self.upstream.requests[0]
        self.assertEqual(body, BODY)

    def test_maps_signature_timestamp_and_delivery(self):
        self.post(headers=self.signed_headers())
        _, headers, _ = self.upstream.requests[0]
        expected_mac = chatwoot_signature("1700000000", BODY)[len("sha256="):]
        self.assertEqual(headers["x-webhook-signature-v2"], expected_mac)
        self.assertEqual(headers["x-webhook-timestamp"], "1700000000")
        self.assertEqual(headers["x-request-id"], "delivery-1")

    def test_mapped_signature_is_a_valid_hermes_v2_signature(self):
        self.post(headers=self.signed_headers())
        _, headers, body = self.upstream.requests[0]
        recomputed = hmac.new(
            SECRET.encode(), headers["x-webhook-timestamp"].encode() + b"." + body, hashlib.sha256
        ).hexdigest()
        self.assertEqual(headers["x-webhook-signature-v2"], recomputed)

    def test_chatwoot_header_names_are_not_forwarded(self):
        self.post(headers=self.signed_headers())
        _, headers, _ = self.upstream.requests[0]
        self.assertFalse(any(name.startswith("x-chatwoot") for name in headers))

    def test_missing_delivery_sends_no_request_id(self):
        self.post(headers=self.signed_headers(delivery=None))
        _, headers, _ = self.upstream.requests[0]
        self.assertNotIn("x-request-id", headers)

    def test_always_forwards_to_the_configured_upstream_path(self):
        self.post(headers=self.signed_headers(), path="/webhooks/other-route?x=1")
        path, _, _ = self.upstream.requests[0]
        self.assertEqual(path, "/webhooks/chatwoot")

    def test_returns_the_upstream_body(self):
        _, body = self.post(headers=self.signed_headers())
        self.assertEqual(json.loads(body), {"status": "accepted"})


class UpstreamStatusTests(RelayCase):
    upstream_status = 401

    def test_passes_an_upstream_rejection_through(self):
        status, _ = self.post(headers=self.signed_headers())
        self.assertEqual(status, 401)


class RejectionTests(RelayCase):
    def test_unsigned_requests_are_refused_and_not_forwarded(self):
        status, body = self.post(headers={"Content-Type": "application/json"})
        self.assertEqual(status, 401)
        self.assertIn("signature", json.loads(body)["error"])
        self.assertEqual(self.upstream.requests, [])

    def test_a_signature_without_timestamp_is_refused(self):
        headers = self.signed_headers()
        del headers["X-Chatwoot-Timestamp"]
        status, _ = self.post(headers=headers)
        self.assertEqual(status, 401)
        self.assertEqual(self.upstream.requests, [])

    def test_oversized_bodies_are_refused_and_not_forwarded(self):
        self.relay.shutdown()
        self.relay.server_close()
        self.start_relay(self.upstream.url, max_bytes=16)
        status, _ = self.post(headers=self.signed_headers())
        self.assertEqual(status, 413)
        self.assertEqual(self.upstream.requests, [])

    def test_health(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.relay.server_address[1], timeout=10)
        connection.request("GET", "/health")
        self.assertEqual(connection.getresponse().status, 200)
        connection.close()


class UnreachableUpstreamTests(unittest.TestCase):
    def test_an_unreachable_upstream_is_a_502(self):
        server = relay.build_server("127.0.0.1", 0, "http://127.0.0.1:9/webhooks/chatwoot")
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=20)
        timestamp = "1700000000"
        connection.request("POST", "/", body=BODY, headers={
            "X-Chatwoot-Timestamp": timestamp,
            "X-Chatwoot-Signature": chatwoot_signature(timestamp, BODY),
        })
        self.assertEqual(connection.getresponse().status, 502)
        connection.close()


class UnitTests(unittest.TestCase):
    def test_map_headers_strips_the_prefix(self):
        mapped = relay.map_headers({"X-Chatwoot-Signature": "sha256=abc", "X-Chatwoot-Timestamp": "5"})
        self.assertEqual(mapped["X-Webhook-Signature-V2"], "abc")

    def test_map_headers_accepts_a_bare_signature(self):
        mapped = relay.map_headers({"X-Chatwoot-Signature": "abc", "X-Chatwoot-Timestamp": "5"})
        self.assertEqual(mapped["X-Webhook-Signature-V2"], "abc")

    def test_chunked_bodies_are_refused(self):
        with self.assertRaises(relay.RelayRejection) as raised:
            relay.read_limited_body({"Transfer-Encoding": "chunked"}, None, 10)
        self.assertEqual(raised.exception.status, 411)

    def test_upstream_must_be_http(self):
        with self.assertRaises(ValueError):
            relay.validate_upstream("file:///etc/passwd")


if __name__ == "__main__":
    unittest.main()
