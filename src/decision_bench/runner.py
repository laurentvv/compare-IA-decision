"""Run one suite against one model: request loop, grading, metrics, JSON output."""

from __future__ import annotations

import json
import math
import threading
from dataclasses import asdict, dataclass
from pathlib import Path

from decision_bench.client import CaseResult, SystemOneClient, build_request
from decision_bench.config import BenchConfig, ModelConfig
from decision_bench.datasets import Case
from decision_bench.metrics import QuestionRecord, summarize
from decision_bench.mock_server import serve as serve_mock
from decision_bench.server import LlamaServerManager

_WARMUP_STATE = "warmup: reply to this one-token state"


def _round_half_up(x: float) -> int:
    return int(math.floor(x + 0.5))


def grade_case(case: Case, result: CaseResult) -> list[QuestionRecord]:
    records: list[QuestionRecord] = []
    for question in case.questions:
        gold = case.gold[question.qid]
        rec = QuestionRecord(case.case_id, question.qid, question.qtype, latency_s=result.latency_s)
        if not result.ok:
            rec.failed = True
            records.append(rec)
            continue
        ans = result.answers.get(question.qid, {})
        if question.qtype == "noul":
            p = float(ans.get("noul", 0.5))
            rec.pred_ptrue = p
            rec.gold_ptrue = gold.ptrue
            rec.pred_probs = {"1": p, "0": 1.0 - p}
            rec.gold_probs = {"1": gold.ptrue, "0": 1.0 - gold.ptrue}
            rec.correct = (p >= 0.5) == (gold.ptrue >= 0.5)
            rec.confidence = max(p, 1.0 - p)
        else:
            probs = {str(k): float(v) for k, v in (ans.get("probabilities") or {}).items()}
            rec.pred_probs = probs
            rec.gold_probs = gold.probs
            if question.qtype == "choice":
                rec.pred_choice = ans.get("choice") or (max(probs, key=probs.get) if probs else None)
                rec.gold_choice = gold.choice
                rec.correct = rec.pred_choice == gold.choice
                rec.confidence = float(ans.get("confidence", max(probs.values(), default=0.0)))
            else:  # score
                rec.pred_score = float(
                    ans.get("score", sum(int(k) * v for k, v in probs.items()) if probs else 0.0)
                )
                rec.gold_level = gold.level
                rec.gold_score = gold.score
                rec.correct = _round_half_up(rec.pred_score) == gold.level
                rec.confidence = float(ans.get("confidence", max(probs.values(), default=0.0)))
        records.append(rec)
    return records


@dataclass
class ModelRun:
    model: str
    suite: str
    backend: str
    n_cases: int
    summary: dict
    error: str | None = None


def _clean(obj: object) -> object:
    if isinstance(obj, float):
        return None if math.isnan(obj) else obj
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean(v) for v in obj]
    return obj


class _MockBackend:
    def __init__(self) -> None:
        self._server = serve_mock("127.0.0.1", 0)
        self._thread: threading.Thread | None = None

    def __enter__(self) -> str:
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def __exit__(self, *_exc: object) -> None:
        self._server.shutdown()
        self._server.server_close()


def _run_cases(client: SystemOneClient, cases: list[Case]) -> tuple[list[QuestionRecord], list[float], list[dict]]:
    records: list[QuestionRecord] = []
    latencies: list[float] = []
    case_log: list[dict] = []
    client.systemone(build_request(_WARMUP_STATE, cases[0].questions[:1]))  # warmup, excluded
    for case in cases:
        request = build_request(case.state, case.questions)
        result = client.ask(case.case_id, request)
        if result.ok:
            latencies.append(result.latency_s)
        records.extend(grade_case(case, result))
        case_log.append(
            {
                "case_id": case.case_id,
                "workflow": case.workflow,
                "ok": result.ok,
                "error": result.error,
                "latency_s": result.latency_s,
                "input_tokens": result.input_tokens,
            }
        )
    return records, latencies, case_log


def run_model(
    cfg: BenchConfig,
    model: ModelConfig,
    suite_name: str,
    cases: list[Case],
    run_dir: Path,
    base_url: str | None = None,
    mock: bool = False,
) -> ModelRun:
    if mock:
        ctx = _MockBackend()
        backend = "mock"
    elif base_url:
        ctx = None
        backend = f"attached:{base_url}"
    else:
        ctx = LlamaServerManager(cfg.server, model, run_dir)
        backend = "llama-server"

    url = base_url or ""
    manager = None
    try:
        if ctx is not None:
            url = ctx.__enter__()
        elif base_url:
            url = base_url
        manager = ctx
        client = SystemOneClient(url, timeout_s=cfg.request_timeout_s)
        try:
            records, latencies, case_log = _run_cases(client, cases)
        finally:
            client.close()
    except Exception as exc:  # server startup failure or fatal client error
        return ModelRun(model.name, suite_name, backend, len(cases), {"error": str(exc)}, error=str(exc))
    finally:
        if manager is not None:
            manager.__exit__(None, None, None)

    summary = summarize(records, latencies, cfg.error_budget)
    summary["backend"] = backend
    payload = _clean(
        {
            "model": model.name,
            "gguf": model.gguf_path,
            "suite": suite_name,
            "backend": backend,
            "n_cases": len(cases),
            "summary": summary,
            "case_log": case_log,
            "records": [asdict(r) for r in records],
        }
    )
    out = run_dir / f"{model.name}__{suite_name}.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return ModelRun(model.name, suite_name, backend, len(cases), summary)
