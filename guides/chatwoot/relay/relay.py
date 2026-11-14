#!/usr/bin/env python3
import argparse
import json
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

DEFAULT_MAX_BODY_BYTES = 1024 * 1024
UPSTREAM_TIMEOUT_SECONDS = 15
CLIENT_TIMEOUT_SECONDS = 10
SIGNATURE_PREFIX = "sha256="


class RelayRejection(Exception):
    def __init__(self, status, reason):
        super().__init__(reason)
        self.status = status
        self.reason = reason


def map_headers(headers):
    signature = (headers.get("X-Chatwoot-Signature") or "").strip()
    timestamp = (headers.get("X-Chatwoot-Timestamp") or "").strip()
    if not signature or not timestamp:
        raise RelayRejection(401, "missing Chatwoot signature or timestamp")
    if signature.startswith(SIGNATURE_PREFIX):
        signature = signature[len(SIGNATURE_PREFIX):]
    mapped = {
        "Content-Type": "application/json",
        "X-Webhook-Signature-V2": signature,
        "X-Webhook-Timestamp": timestamp,
    }
    delivery = (headers.get("X-Chatwoot-Delivery") or "").strip()
    if delivery:
        mapped["X-Request-ID"] = delivery
    return mapped


def read_limited_body(headers, stream, max_bytes):
    if headers.get("Transfer-Encoding"):
        raise RelayRejection(411, "chunked bodies are not accepted; send Content-Length")
    raw_length = headers.get("Content-Length")
    if raw_length is None:
        raise RelayRejection(411, "Content-Length is required")
    try:
        length = int(raw_length)
    except ValueError:
        raise RelayRejection(400, "invalid Content-Length") from None
    if length < 0:
        raise RelayRejection(400, "invalid Content-Length")
    if length > max_bytes:
        raise RelayRejection(413, f"body larger than {max_bytes} bytes")
    return stream.read(length)


def forward(upstream, body, headers, opener=urllib.request.urlopen):
    request = urllib.request.Request(upstream, data=body, headers=headers, method="POST")
    try:
        with opener(request, timeout=UPSTREAM_TIMEOUT_SECONDS) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()
    except (urllib.error.URLError, OSError) as error:
        raise RelayRejection(502, f"upstream unreachable: {error}") from None


def make_handler(upstream, max_bytes, opener=urllib.request.urlopen):
    class RelayHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        timeout = CLIENT_TIMEOUT_SECONDS

        def log_message(self, format, *args):
            sys.stderr.write("relay: " + (format % args) + "\n")

        def reply(self, status, body):
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def reject(self, rejection):
            self.close_connection = True
            self.reply(rejection.status, json.dumps({"error": rejection.reason}).encode("utf-8"))

        def do_GET(self):
            if self.path == "/health":
                self.reply(200, b'{"status": "ok"}')
            else:
                self.reject(RelayRejection(404, "not found"))

        def do_POST(self):
            try:
                body = read_limited_body(self.headers, self.rfile, max_bytes)
                mapped = map_headers(self.headers)
                status, upstream_body = forward(upstream, body, mapped, opener)
            except RelayRejection as rejection:
                self.reject(rejection)
                return
            self.reply(status, upstream_body)

    return RelayHandler


def validate_upstream(url):
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError(f"upstream must be an http or https URL: {url!r}")
    return url


def build_server(host, port, upstream, max_bytes=DEFAULT_MAX_BODY_BYTES, opener=urllib.request.urlopen):
    return ThreadingHTTPServer((host, port), make_handler(validate_upstream(upstream), max_bytes, opener))


def build_parser():
    parser = argparse.ArgumentParser(
        description="Relay Chatwoot webhooks to one Hermes webhook route, renaming the signature headers."
    )
    parser.add_argument("--upstream", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8645)
    parser.add_argument("--max-body-bytes", type=int, default=DEFAULT_MAX_BODY_BYTES)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        server = build_server(args.host, args.port, args.upstream, args.max_body_bytes)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(f"relay: listening on {args.host}:{server.server_address[1]}, forwarding to {args.upstream}", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
