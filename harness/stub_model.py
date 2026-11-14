#!/usr/bin/env python3
import argparse
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

MODEL_ID = "casebook-stub"
CONTEXT_LENGTH = 200000
DEFAULT_REPLY = "Acknowledged."
MAX_BODY_BYTES = 8 * 1024 * 1024


class Recorder:
    def __init__(self, log_path):
        self.log_path = Path(log_path)
        self.lock = threading.Lock()
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.touch()

    def record(self, entry):
        line = json.dumps(entry, sort_keys=True)
        with self.lock, self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def models_payload():
    return {
        "object": "list",
        "data": [
            {
                "id": MODEL_ID,
                "object": "model",
                "created": 0,
                "owned_by": "casebook",
                "context_length": CONTEXT_LENGTH,
            }
        ],
    }


def usage_for(reply):
    completion_tokens = max(1, len(reply.split()))
    return {"prompt_tokens": 1, "completion_tokens": completion_tokens, "total_tokens": 1 + completion_tokens}


def completion_payload(model, reply, created):
    return {
        "id": "chatcmpl-casebook",
        "object": "chat.completion",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": reply},
                "finish_reason": "stop",
            }
        ],
        "usage": usage_for(reply),
    }


def stream_chunks(model, reply, created):
    base = {"id": "chatcmpl-casebook", "object": "chat.completion.chunk", "created": created, "model": model}
    yield dict(base, choices=[{"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}])
    yield dict(base, choices=[{"index": 0, "delta": {"content": reply}, "finish_reason": None}])
    yield dict(base, choices=[{"index": 0, "delta": {}, "finish_reason": "stop"}])
    yield dict(base, choices=[], usage=usage_for(reply))


def message_text(message):
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(part.get("text", "") for part in content if isinstance(part, dict))
    return ""


def request_text(record):
    body = record.get("body") or {}
    return "\n".join(message_text(message) for message in body.get("messages", []) if isinstance(message, dict))


def read_records(log_path):
    path = Path(log_path)
    if not path.is_file():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("path", "").endswith("/chat/completions"):
            records.append(record)
    return records


def make_handler(recorder, reply):
    class StubHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format, *args):
            return

        def send_json(self, status, payload):
            data = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def read_body(self):
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY_BYTES:
                return None
            raw = self.rfile.read(length) if length else b""
            try:
                return json.loads(raw) if raw else {}
            except ValueError:
                return None

        def do_GET(self):
            recorder.record({"method": "GET", "path": self.path, "time": time.time()})
            if self.path.rstrip("/").endswith("/models"):
                self.send_json(200, models_payload())
            elif self.path.rstrip("/") == "/health":
                self.send_json(200, {"status": "ok"})
            else:
                self.send_json(404, {"error": {"message": "not found"}})

        def do_POST(self):
            body = self.read_body()
            recorder.record({"method": "POST", "path": self.path, "time": time.time(), "body": body})
            if body is None:
                self.send_json(400, {"error": {"message": "invalid JSON body"}})
                return
            if not self.path.rstrip("/").endswith("/chat/completions"):
                self.send_json(404, {"error": {"message": "not found"}})
                return
            model = body.get("model") or MODEL_ID
            created = int(time.time())
            if body.get("stream"):
                self.send_stream(model, created)
            else:
                self.send_json(200, completion_payload(model, reply, created))

        def send_stream(self, model, created):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()
            for chunk in stream_chunks(model, reply, created):
                self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode("utf-8"))
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
            self.close_connection = True

    return StubHandler


def build_server(host, port, log_path, reply=DEFAULT_REPLY):
    return ThreadingHTTPServer((host, port), make_handler(Recorder(log_path), reply))


def serve(args):
    server = build_server(args.host, args.port, args.log, args.reply)
    if args.port_file:
        Path(args.port_file).write_text(str(server.server_address[1]), encoding="utf-8")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def print_text(args):
    records = read_records(args.log)
    if args.index >= len(records):
        print(f"no chat request with index {args.index}; {len(records)} recorded", file=sys.stderr)
        return 1
    print(request_text(records[args.index]))
    return 0


def print_count(args):
    print(len(read_records(args.log)))
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="An OpenAI-compatible stub model that records every request.")
    commands = parser.add_subparsers(dest="command", required=True)
    serve_parser = commands.add_parser("serve")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=0)
    serve_parser.add_argument("--log", required=True)
    serve_parser.add_argument("--port-file")
    serve_parser.add_argument("--reply", default=DEFAULT_REPLY)
    serve_parser.set_defaults(handler=serve)
    text_parser = commands.add_parser("text")
    text_parser.add_argument("--log", required=True)
    text_parser.add_argument("index", type=int)
    text_parser.set_defaults(handler=print_text)
    count_parser = commands.add_parser("count")
    count_parser.add_argument("--log", required=True)
    count_parser.set_defaults(handler=print_count)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
