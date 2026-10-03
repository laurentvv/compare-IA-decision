"""Deterministic mock of POST /v1/systemone for offline pipeline validation.

Probabilities are derived from sha256(state + question id): same request -> same answers,
different cases -> varied answers. Enough to exercise client, grading, metrics, report —
never a claim about model quality.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections.abc import Mapping
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_MOCK_MODEL = "mock"


def _uniform_unit(size: int, seed: bytes) -> list[float]:
    weights = []
    for i in range(size):
        digest = hashlib.sha256(seed + b":" + str(i).encode()).digest()
        weights.append((int.from_bytes(digest[:8], "big") + 1) / 2**64)
    total = sum(weights)
    return [w / total for w in weights]


def _answer(qid: str, question: dict, state_text: str) -> dict:
    seed = hashlib.sha256(state_text.encode("utf-8") + b"|" + qid.encode()).digest()
    qtype = question.get("type")
    if qtype == "noul":
        digest = hashlib.sha256(seed).digest()
        return {"type": "noul", "noul": int.from_bytes(digest[:8], "big") / 2**64}
    criteria = question.get("criteria")
    if qtype == "choice":
        options = sorted(criteria.keys()) if isinstance(criteria, Mapping) else None
        if not options:
            options = [f"option_{i}" for i in range(2)]
        probs = _uniform_unit(len(options), seed)
    elif qtype == "score":
        levels = criteria if isinstance(criteria, list) else ["low", "high"]
        probs = _uniform_unit(len(levels), seed)
    else:
        return {"type": "noul", "noul": 0.5}
    peak = max(range(len(probs)), key=lambda i: probs[i])
    distribution = {str(i) if qtype == "score" else options[i]: p for i, p in enumerate(probs)}
    answer: dict = {"type": qtype, "probabilities": distribution}
    if qtype == "choice":
        answer["choice"] = options[peak]
        answer["confidence"] = max(probs)
    else:
        answer["score"] = sum(i * p for i, p in enumerate(probs))
        answer["legend"] = {str(i): level for i, level in enumerate(levels)}
        answer["confidence"] = max(probs)
    return answer


class MockHandler(BaseHTTPRequestHandler):
    delay_s = 0.002

    def log_message(self, fmt: str, *args: object) -> None:  # silence stderr in tests
        pass

    def _send(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 (http.server API)
        if self.path == "/health":
            self._send(200, {"status": "ok"})
        else:
            self._send(404, {"error": {"message": "not found"}})

    def do_POST(self) -> None:  # noqa: N802 (http.server API)
        if self.path != "/v1/systemone":
            self._send(404, {"error": {"message": "not found"}})
            return
        length = int(self.headers.get("Content-Length", "0"))
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send(400, {"error": {"message": "invalid JSON"}})
            return
        if "state" not in body or not isinstance(body.get("questions"), dict) or not body["questions"]:
            self._send(400, {"error": {"message": "state and non-empty questions are required"}})
            return
        time.sleep(self.delay_s)
        state_text = body["state"] if isinstance(body["state"], str) else json.dumps(body["state"], sort_keys=True)
        answers = {qid: _answer(qid, q, state_text) for qid, q in body["questions"].items()}
        self._send(
            200,
            {
                "model": _MOCK_MODEL,
                "answers": answers,
                "usage": {"input_tokens": max(1, len(state_text) // 4), "output_tokens": 0},
            },
        )


def serve(host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), MockHandler)
    server.daemon_threads = True
    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="Deterministic mock of POST /v1/systemone")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8099)
    args = parser.parse_args()
    server = serve(args.host, args.port)
    print(f"mock /v1/systemone on http://{args.host}:{server.server_address[1]}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    main()
