import contextlib
import io
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from harness import stub_model


class StubServerCase(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.log = Path(self.directory.name) / "stub.jsonl"
        self.server = stub_model.build_server("127.0.0.1", 0, self.log, reply="stub reply")
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def post(self, path, payload):
        data = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        request = urllib.request.Request(
            self.base + path, data=data, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, response.headers.get("Content-Type"), response.read().decode()
        except urllib.error.HTTPError as error:
            return error.code, error.headers.get("Content-Type"), error.read().decode()

    def get(self, path):
        try:
            with urllib.request.urlopen(self.base + path, timeout=10) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    def records(self):
        return [json.loads(line) for line in self.log.read_text().splitlines() if line.strip()]


class ModelsTests(StubServerCase):
    def test_lists_one_model_with_a_context_length(self):
        status, payload = self.get("/v1/models")
        self.assertEqual(status, 200)
        self.assertEqual(payload["data"][0]["id"], stub_model.MODEL_ID)
        self.assertGreaterEqual(payload["data"][0]["context_length"], 64000)

    def test_unknown_get_is_404_and_recorded(self):
        status, _ = self.get("/v1/props")
        self.assertEqual(status, 404)
        self.assertEqual(self.records()[-1]["path"], "/v1/props")


class CompletionTests(StubServerCase):
    def test_non_streaming_reply(self):
        status, content_type, body = self.post(
            "/v1/chat/completions", {"model": "m", "messages": [{"role": "user", "content": "hi"}]}
        )
        self.assertEqual(status, 200)
        self.assertEqual(content_type, "application/json")
        payload = json.loads(body)
        self.assertEqual(payload["choices"][0]["message"]["content"], "stub reply")
        self.assertEqual(payload["choices"][0]["finish_reason"], "stop")
        self.assertEqual(payload["model"], "m")

    def test_streaming_reply_is_server_sent_events(self):
        status, content_type, body = self.post(
            "/v1/chat/completions", {"model": "m", "stream": True, "messages": []}
        )
        self.assertEqual(status, 200)
        self.assertEqual(content_type, "text/event-stream")
        events = [line[len("data: "):] for line in body.splitlines() if line.startswith("data: ")]
        self.assertEqual(events[-1], "[DONE]")
        chunks = [json.loads(event) for event in events[:-1]]
        text = "".join(
            choice["delta"].get("content", "") for chunk in chunks for choice in chunk["choices"]
        )
        self.assertEqual(text, "stub reply")
        self.assertIn("stop", [c["finish_reason"] for chunk in chunks for c in chunk["choices"]])
        self.assertIn("usage", chunks[-1])

    def test_records_the_request_body(self):
        messages = [{"role": "system", "content": "SYSTEM-MARK"}, {"role": "user", "content": "USER-MARK"}]
        self.post("/v1/chat/completions", {"model": "m", "messages": messages})
        record = self.records()[-1]
        self.assertEqual(record["method"], "POST")
        self.assertEqual(record["body"]["messages"], messages)

    def test_accepts_a_base_url_without_v1(self):
        status, _, _ = self.post("/chat/completions", {"model": "m", "messages": []})
        self.assertEqual(status, 200)

    def test_invalid_json_is_400_and_still_recorded(self):
        status, _, _ = self.post("/v1/chat/completions", b"{not json")
        self.assertEqual(status, 400)
        self.assertIsNone(self.records()[-1]["body"])

    def test_unknown_post_is_404(self):
        status, _, _ = self.post("/v1/responses", {"input": "x"})
        self.assertEqual(status, 404)


class TextTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.log = Path(self.directory.name) / "stub.jsonl"
        records = [
            {"method": "GET", "path": "/v1/models"},
            {"method": "POST", "path": "/v1/chat/completions", "body": {"messages": [
                {"role": "system", "content": "first system"},
                {"role": "user", "content": [{"type": "text", "text": "first user"}]},
            ]}},
            {"method": "POST", "path": "/v1/chat/completions", "body": {"messages": [
                {"role": "user", "content": "second user"},
                {"role": "assistant", "content": None},
            ]}},
        ]
        self.log.write_text("".join(json.dumps(record) + "\n" for record in records))

    def run_cli(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = stub_model.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_count_ignores_non_chat_requests(self):
        self.assertEqual(self.run_cli(["count", "--log", str(self.log)])[1].strip(), "2")

    def test_count_of_a_missing_log_is_zero(self):
        missing = Path(self.directory.name) / "missing.jsonl"
        self.assertEqual(self.run_cli(["count", "--log", str(missing)])[1].strip(), "0")

    def test_text_joins_string_and_part_contents(self):
        code, out, _ = self.run_cli(["text", "--log", str(self.log), "0"])
        self.assertEqual(code, 0)
        self.assertEqual(out, "first system\nfirst user\n")

    def test_text_tolerates_null_content(self):
        self.assertEqual(self.run_cli(["text", "--log", str(self.log), "1"])[1], "second user\n\n")

    def test_text_out_of_range_fails(self):
        code, _, err = self.run_cli(["text", "--log", str(self.log), "5"])
        self.assertEqual(code, 1)
        self.assertIn("2 recorded", err)


if __name__ == "__main__":
    unittest.main()
