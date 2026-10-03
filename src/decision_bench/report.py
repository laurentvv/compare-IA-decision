"""Markdown + stdout reporting across models for one bench run."""

from __future__ import annotations

import math
from pathlib import Path

from decision_bench.runner import ModelRun

_COLUMNS = [
    ("accuracy", "acc"),
    ("macro_f1", "F1"),
    ("brier", "Brier"),
    ("nll", "NLL"),
    ("ece_toplabel_10bins", "ECE10"),
    ("mean_kl_vs_gold", "KL"),
    ("coverage_at_5%_error", "cov@5%"),
    ("latency_p50_s", "p50 s"),
    ("latency_p95_s", "p95 s"),
    ("failures", "fails"),
]


def _fmt(value: object) -> str:
    if isinstance(value, float):
        return "—" if math.isnan(value) else f"{value:.3f}"
    if value is None:
        return "—"
    return str(value)


def _type_accuracy(run: ModelRun, qtype: str) -> str:
    block = run.summary.get("by_type", {}).get(qtype)
    return "—" if not block else _fmt(block["accuracy"])


def render_summary_md(runs: list[ModelRun], suite: str, n_cases: int, error_budget: float) -> str:
    lines = [
        "# Decision models comparison",
        "",
        f"- Suite: `{suite}` ({n_cases} cases)",
        "- Quantization: Q8_0 for every model (matched-weights comparison rule).",
        "- Grading: choice=argmax vs gold; score=round(expected) vs gold level (+MAE in JSON); noul=p(true)>=0.5.",
        "- Probabilities are NOT guaranteed calibrated (llama.cpp scales them with per-model temperatures);",
        "  read Brier/NLL/ECE/KL alongside accuracy, per the typed-decisions dataset card.",
        "",
        "| model | acc | acc choice | acc score | acc noul | " + " | ".join(c[1] for c in _COLUMNS) + " |",
        "|---|---|---|---|---|" + "---|" * len(_COLUMNS),
    ]
    for run in runs:
        if run.error:
            lines.append(f"| {run.model} | ERROR: {run.error[:80]} | " + " | " * (len(_COLUMNS) + 3) + "|")
            continue
        cells = [_fmt(run.summary.get(key)) for key, _label in _COLUMNS]
        accs = (
            f"| {run.model} | {_fmt(run.summary.get('accuracy'))} "
            f"| {_type_accuracy(run, 'choice')} | {_type_accuracy(run, 'score')} "
            f"| {_type_accuracy(run, 'noul')} "
        )
        lines.append(accs + "| " + " | ".join(cells) + " |")
    lines += [
        "",
        "Notes:",
        "- Failed requests are counted in `fails` and stay in the denominator (no silent retry).",
        f"- `cov@{error_budget:.0%}` = share of questions automatable at empirical error"
        f" <= {error_budget:.0%} (highest confidence first).",
        "- Latency is per-case (one HTTP request with all questions of the case), warmup excluded.",
        "",
    ]
    return "\n".join(lines)


def write_summary_md(runs: list[ModelRun], suite: str, n_cases: int, error_budget: float, run_dir: Path) -> Path:
    out = run_dir / "summary.md"
    out.write_text(render_summary_md(runs, suite, n_cases, error_budget), encoding="utf-8")
    return out


def print_table(runs: list[ModelRun]) -> str:
    header = f"{'model':<12} {'acc':>7} {'choice':>7} {'score':>7} {'noul':>7} {'p50 s':>8} {'p95 s':>8} {'fails':>6}"
    rows = [header, "-" * len(header)]
    for run in runs:
        if run.error:
            rows.append(f"{run.model:<12} ERROR: {run.error[:60]}")
            continue
        by_type = run.summary.get("by_type", {})
        rows.append(
            f"{run.model:<12} {_fmt(run.summary.get('accuracy')):>7} "
            f"{_fmt(by_type.get('choice', {}).get('accuracy')):>7} "
            f"{_fmt(by_type.get('score', {}).get('accuracy')):>7} "
            f"{_fmt(by_type.get('noul', {}).get('accuracy')):>7} "
            f"{_fmt(run.summary.get('latency_p50_s')):>8} {_fmt(run.summary.get('latency_p95_s')):>8} "
            f"{run.summary.get('failures', 0):>6}"
        )
    return "\n".join(rows)
