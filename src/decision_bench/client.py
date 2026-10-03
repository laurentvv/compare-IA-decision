"""HTTP client for POST /v1/systemone (llama.cpp PR #29818, TypeSafe-compatible).

Request/response shapes follow the pinned upstream docs:
- scratch/upstream_docs/llama-cpp/server-README_master_cb7934c.md (llama.cpp, errors: HTTP 400)
- scratch/upstream_docs/models/typesafe-api.md (hosted reference, errors: HTTP 422)

Protocol rule (jev-benchmarks): failed requests are counted, never silently retried.
"""

from __future__ import annotations

import json
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import httpx

VALID_TYPES = ("choice", "score", "noul")
_PROB_SUM_TOL = 0.02


class SystemOneError(RuntimeError):
    """A /v1/systemone request failed (transport, HTTP status, or invalid answer shape)."""


@dataclass
class Question:
    """One typed question about the state."""

    qid: str
    qtype: str
    instructions: str
    # choice -> {option: description|None}; score -> [level, ...] (lowest first);
    # noul -> {"true": ..., "false": ...} (optional)
    criteria: Mapping[str, str | None] | list[str] | Mapping[str, str] | None = None

    def to_api(self) -> dict[str, Any]:
        if self.qtype not in VALID_TYPES:
            raise ValueError(f"question {self.qid!r}: type {self.qtype!r} not in {VALID_TYPES}")
        if not self.instructions:
            raise ValueError(f"question {self.qid!r}: empty instructions")
        q: dict[str, Any] = {"type": self.qtype, "instructions": self.instructions}
        if self.criteria is not None:
            if self.qtype == "choice" and not isinstance(self.criteria, Mapping):
                raise ValueError(f"question {self.qid!r}: choice criteria must be a map option->description")
            if self.qtype == "score" and not isinstance(self.criteria, list):
                raise ValueError(f"question {self.qid!r}: score criteria must be an ordered list of levels")
            q["criteria"] = self.criteria
        return q


def build_request(state: Any, questions: list[Question]) -> dict[str, Any]:
    """Build the exact body of one POST /v1/systemone request: {state, questions}.

    All questions of a case go into ONE request (parallel evaluation, dataset-card guidance).
    """
    if not questions:
        raise ValueError("a case must carry at least one question")
    return {"state": state, "questions": {q.qid: q.to_api() for q in questions}}


@dataclass
class CaseResult:
    case_id: str
    ok: bool
    error: str | None
    latency_s: float
    input_tokens: int | None
    answers: dict[str, Any]
    resp_model: str | None = None  # server-reported model field (identity evidence)


def validate_response(request: dict[str, Any], data: dict[str, Any]) -> None:
    """Integrity control from the jev-benchmarks protocol: every question must come back
    with the right type and a finite probability vector summing to 1."""
    answers = data.get("answers")
    if not isinstance(answers, dict):
        raise SystemOneError(f"response has no answers map: {str(data)[:200]}")
    for qid, question in request["questions"].items():
        if qid not in answers:
            raise SystemOneError(f"missing answer for question {qid!r}")
        ans = answers[qid]
        if ans.get("type") != question["type"]:
            raise SystemOneError(f"answer {qid!r}: type {ans.get('type')!r} != {question['type']!r}")
        if question["type"] == "noul":
            p = ans.get("noul")
            if not isinstance(p, (int, float)) or not 0.0 <= float(p) <= 1.0:
                raise SystemOneError(f"answer {qid!r}: noul probability {p!r} out of range")
            continue
        probs = ans.get("probabilities")
        if not isinstance(probs, dict) or not probs:
            raise SystemOneError(f"answer {qid!r}: missing probabilities")
        if any(not isinstance(v, (int, float)) or float(v) < 0.0 for v in probs.values()):
            raise SystemOneError(f"answer {qid!r}: negative probability")
        total = sum(float(v) for v in probs.values())
        if abs(total - 1.0) > _PROB_SUM_TOL:
            raise SystemOneError(f"answer {qid!r}: probabilities sum to {total:.4f}")


class SystemOneClient:
    """Thin httpx wrapper. No retries: failures surface as ok=False CaseResults."""

    def __init__(self, base_url: str, timeout_s: float = 60.0) -> None:
        self._http = httpx.Client(base_url=base_url, timeout=timeout_s)

    def close(self) -> None:
        self._http.close()

    def health(self) -> bool:
        try:
            return self._http.get("/health").status_code == 200
        except httpx.HTTPError:
            return False

    def systemone(self, request: dict[str, Any]) -> tuple[dict[str, Any], float, int | None]:
        t0 = time.perf_counter()
        resp = self._http.post("/v1/systemone", json=request)
        latency = time.perf_counter() - t0
        if resp.status_code != 200:
            raise SystemOneError(f"HTTP {resp.status_code}: {resp.text[:300]}")
        try:
            data = resp.json()
        except json.JSONDecodeError as exc:
            raise SystemOneError(f"non-JSON response: {exc}") from exc
        validate_response(request, data)
        usage = data.get("usage") or {}
        tokens = usage.get("input_tokens")
        return data, latency, int(tokens) if isinstance(tokens, (int, float)) else None

    def ask(self, case_id: str, request: dict[str, Any]) -> CaseResult:
        try:
            data, latency, tokens = self.systemone(request)
        except (SystemOneError, httpx.HTTPError) as exc:
            return CaseResult(
                case_id, ok=False, error=str(exc), latency_s=0.0, input_tokens=None, answers={}, resp_model=None
            )
        return CaseResult(
            case_id,
            ok=True,
            error=None,
            latency_s=latency,
            input_tokens=tokens,
            answers=data.get("answers", {}),
            resp_model=data.get("model"),
        )
