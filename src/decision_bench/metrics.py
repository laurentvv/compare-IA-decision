"""Metrics (contract C7) over per-question QuestionRecord rows.

Conventions (pinned by tests/test_metrics.py, hand-computed values):
- Brier (multiclass, soft gold): mean over valid questions of the SUM of squared
  errors across classes, sum_c (p_c - g_c)^2 (noul = the 2-class case).
- NLL: mean of -sum_c g_c * ln(max(p_c, eps)).
- KL: mean of sum_c g_c * ln(max(g_c, eps) / max(p_c, eps)) — gold || pred.
- ECE: top-label expected calibration error, 10 equal-width bins ([0,.1) ... [.9,1])
  on the recorded confidence.
- Coverage at error budget: largest prefix of valid questions sorted by confidence
  (descending) whose empirical error rate <= budget, as a fraction of ALL questions.
- accuracy: correct / answered, failures excluded from the numerator (and tracked
  separately); NaN when nothing was answered.
- Latency percentiles: nearest-rank on sorted values.
- Failed questions carry no predictions: they are excluded from probability
  metrics, counted in `failures`, and stay in `n_questions` (C13: reported, never
  silently retried).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

EPS = 1e-12
ECE_BINS = 10


@dataclass
class QuestionRecord:
    """One graded question of one case (one row per question, per model, per suite)."""

    case_id: str
    qid: str
    qtype: str
    latency_s: float = 0.0
    failed: bool = False
    correct: bool | None = None
    confidence: float | None = None
    pred_probs: dict[str, float] = field(default_factory=dict)
    gold_probs: dict[str, float] = field(default_factory=dict)
    pred_choice: str | None = None
    gold_choice: str | None = None
    pred_score: float | None = None
    gold_level: int | None = None
    gold_score: float | None = None
    pred_ptrue: float | None = None
    gold_ptrue: float | None = None


def _valid(records: list[QuestionRecord]) -> list[QuestionRecord]:
    return [r for r in records if not r.failed]


def _dists(records: list[QuestionRecord]) -> list[tuple[dict[str, float], dict[str, float]]]:
    pairs = []
    for r in _valid(records):
        if r.pred_probs and r.gold_probs:
            keys = sorted(set(r.pred_probs) | set(r.gold_probs))
            pairs.append(
                (
                    {k: float(r.gold_probs.get(k, 0.0)) for k in keys},
                    {k: float(r.pred_probs.get(k, 0.0)) for k in keys},
                )
            )
    return pairs


def accuracy(records: list[QuestionRecord]) -> float:
    answered = [r for r in _valid(records) if r.correct is not None]
    if not answered:
        return math.nan
    return sum(1 for r in answered if r.correct) / len(answered)


def macro_f1(records: list[QuestionRecord]) -> float:
    graded = [(r.gold_choice, r.pred_choice) for r in _valid(records) if r.gold_choice and r.pred_choice]
    if not graded:
        return math.nan
    labels = sorted({g for g, _ in graded} | {p for _, p in graded})
    scores = []
    for label in labels:
        tp = sum(1 for g, p in graded if g == label and p == label)
        fp = sum(1 for g, p in graded if g != label and p == label)
        fn = sum(1 for g, p in graded if g == label and p != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        scores.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return sum(scores) / len(scores)


def brier(records: list[QuestionRecord]) -> float:
    pairs = _dists(records)
    if not pairs:
        return math.nan
    total = 0.0
    for gold, pred in pairs:
        total += sum((pred[k] - gold[k]) ** 2 for k in gold)
    return total / len(pairs)


def nll(records: list[QuestionRecord]) -> float:
    pairs = _dists(records)
    if not pairs:
        return math.nan
    total = 0.0
    for gold, pred in pairs:
        total -= sum(gold[k] * math.log(max(pred[k], EPS)) for k in gold if gold[k] > 0)
    return total / len(pairs)


def mean_kl(records: list[QuestionRecord]) -> float:
    pairs = _dists(records)
    if not pairs:
        return math.nan
    total = 0.0
    for gold, pred in pairs:
        total += sum(gold[k] * math.log(max(gold[k], EPS) / max(pred[k], EPS)) for k in gold if gold[k] > 0)
    return total / len(pairs)


def ece_toplabel(records: list[QuestionRecord]) -> float:
    graded = [(r.confidence, bool(r.correct)) for r in _valid(records) if r.confidence is not None]
    if not graded:
        return math.nan
    bins: list[list[tuple[float, bool]]] = [[] for _ in range(ECE_BINS)]
    for conf, ok in graded:
        bins[min(int(conf * ECE_BINS), ECE_BINS - 1)].append((conf, ok))
    ece = 0.0
    for bucket in bins:
        if not bucket:
            continue
        mean_conf = sum(c for c, _ in bucket) / len(bucket)
        mean_acc = sum(1 for _, ok in bucket if ok) / len(bucket)
        ece += (len(bucket) / len(graded)) * abs(mean_acc - mean_conf)
    return ece


def coverage_at_error(records: list[QuestionRecord], budget: float) -> float:
    graded = [(r.confidence, bool(r.correct)) for r in _valid(records) if r.confidence is not None]
    if not graded:
        return math.nan
    errors = 0
    coverage = 0.0
    for count, (_conf, ok) in enumerate(
        sorted(graded, key=lambda pair: pair[0], reverse=True), start=1
    ):
        errors += 0 if ok else 1
        if errors / count <= budget:
            coverage = count / len(graded)
        else:
            break
    return coverage


def score_mae(records: list[QuestionRecord]) -> float:
    graded = [
        (r.pred_score, r.gold_score)
        for r in _valid(records)
        if r.qtype == "score" and r.pred_score is not None and r.gold_score is not None
    ]
    if not graded:
        return math.nan
    return sum(abs(pred - gold) for pred, gold in graded) / len(graded)


def latency_percentiles(values: list[float]) -> tuple[float, float]:
    """Nearest-rank p50 and p95 of the sorted values."""

    def at(quantile: float) -> float:
        ordered = sorted(values)
        rank = max(1, math.ceil(quantile * len(ordered)))
        return ordered[rank - 1]

    if not values:
        return math.nan, math.nan
    return at(0.50), at(0.95)


def _type_block(records: list[QuestionRecord], qtype: str, budget: float) -> dict:
    subset = [r for r in records if r.qtype == qtype]
    block: dict = {
        "n": len(subset),
        "failures": sum(1 for r in subset if r.failed),
        "accuracy": accuracy(subset),
        "brier": brier(subset),
        "nll": nll(subset),
        "ece_toplabel_10bins": ece_toplabel(subset),
        "mean_kl_vs_gold": mean_kl(subset),
        f"coverage_at_{budget:.0%}_error": coverage_at_error(subset, budget),
    }
    if qtype == "choice":
        block["macro_f1"] = macro_f1(subset)
    if qtype == "score":
        block["score_mae"] = score_mae(subset)
    return block


def summarize(records: list[QuestionRecord], latencies: list[float], error_budget: float = 0.05) -> dict:
    """Aggregate one model run: overall + per-question-type blocks (contract C11)."""
    p50, p95 = latency_percentiles(latencies)
    return {
        "n_questions": len(records),
        "failures": sum(1 for r in records if r.failed),
        "accuracy": accuracy(records),
        "macro_f1": macro_f1(records),
        "brier": brier(records),
        "nll": nll(records),
        "ece_toplabel_10bins": ece_toplabel(records),
        "mean_kl_vs_gold": mean_kl(records),
        f"coverage_at_{error_budget:.0%}_error": coverage_at_error(records, error_budget),
        "latency_p50_s": p50,
        "latency_p95_s": p95,
        "by_type": {qtype: _type_block(records, qtype, error_budget) for qtype in sorted({r.qtype for r in records})},
    }
