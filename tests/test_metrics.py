"""Hand-computed expectations for every metric (contract C7)."""

from __future__ import annotations

import math

from decision_bench.metrics import (
    QuestionRecord,
    accuracy,
    brier,
    coverage_at_error,
    ece_toplabel,
    latency_percentiles,
    macro_f1,
    mean_kl,
    nll,
    score_mae,
    summarize,
)


def _rec(
    qtype: str,
    correct: bool | None,
    confidence: float | None = None,
    pred_probs: dict[str, float] | None = None,
    gold_probs: dict[str, float] | None = None,
    pred_choice: str | None = None,
    gold_choice: str | None = None,
    pred_score: float | None = None,
    gold_score: float | None = None,
    failed: bool = False,
) -> QuestionRecord:
    return QuestionRecord(
        case_id="c",
        qid="q",
        qtype=qtype,
        failed=failed,
        correct=correct,
        confidence=confidence,
        pred_probs=pred_probs or {},
        gold_probs=gold_probs or {},
        pred_choice=pred_choice,
        gold_choice=gold_choice,
        pred_score=pred_score,
        gold_score=gold_score,
    )


def test_accuracy_ignores_failures() -> None:
    records = [
        _rec("choice", True),
        _rec("choice", False),
        _rec("choice", None, failed=True),
    ]
    assert accuracy(records) == 0.5


def test_accuracy_empty_is_nan() -> None:
    assert math.isnan(accuracy([]))


def test_macro_f1_two_labels() -> None:
    # label a: tp=1 fp=0 fn=1 -> F1=2/3 ; label b: tp=1 fp=1 fn=0 -> F1=2/3 ; macro=2/3
    records = [
        _rec("choice", True, pred_choice="a", gold_choice="a"),
        _rec("choice", False, pred_choice="b", gold_choice="a"),
        _rec("choice", True, pred_choice="b", gold_choice="b"),
    ]
    assert math.isclose(macro_f1(records), 2 / 3)


def test_brier_multiclass_hand_computed() -> None:
    # q1: pred (0.8, 0.2) gold (1, 0): (0.2^2 + 0.2^2) = 0.08
    # q2: pred (0.5, 0.5) gold (0, 1): (0.5^2 + 0.5^2) = 0.50
    records = [
        _rec("choice", True, pred_probs={"a": 0.8, "b": 0.2}, gold_probs={"a": 1.0, "b": 0.0}),
        _rec("choice", False, pred_probs={"a": 0.5, "b": 0.5}, gold_probs={"a": 0.0, "b": 1.0}),
    ]
    assert math.isclose(brier(records), (0.08 + 0.50) / 2)


def test_nll_hand_computed() -> None:
    records = [
        _rec("choice", True, pred_probs={"a": 0.5, "b": 0.5}, gold_probs={"a": 1.0}),
    ]
    assert math.isclose(nll(records), -math.log(0.5))


def test_ece_toplabel_perfect_confidence() -> None:
    records = [_rec("choice", True, confidence=0.9), _rec("choice", False, confidence=0.4)]
    # bin [0.4,0.5): conf 0.4 acc 0 -> |0-0.4| * 1/2 ; bin [0.9,1.0]: conf 0.9 acc 1 -> 0.1 * 1/2
    assert math.isclose(ece_toplabel(records), 0.4 * 0.5 + 0.1 * 0.5)


def test_mean_kl_hand_computed() -> None:
    # KL(gold || pred) with gold (1, 0), pred (0.5, 0.5): 1 * ln(1 / 0.5) = ln 2
    records = [_rec("choice", True, pred_probs={"a": 0.5, "b": 0.5}, gold_probs={"a": 1.0, "b": 0.0})]
    assert math.isclose(mean_kl(records), math.log(2))


def test_coverage_at_error_budget() -> None:
    # confidences 0.9 (ok), 0.8 (ok), 0.3 (wrong), 0.2 (wrong) at budget 50%:
    # prefix 1: err 0% ok ; prefix 2: 0% ok ; prefix 3: 33% ok ; prefix 4: 50% ok -> coverage 1.0
    records = [
        _rec("choice", True, confidence=0.9),
        _rec("choice", True, confidence=0.8),
        _rec("choice", False, confidence=0.3),
        _rec("choice", False, confidence=0.2),
    ]
    assert coverage_at_error(records, budget=0.5) == 1.0
    # budget 10%: prefixes 1-2 qualify (0% error) -> coverage 0.5
    assert coverage_at_error(records, budget=0.1) == 0.5


def test_score_mae() -> None:
    records = [
        _rec("score", True, pred_score=2.1, gold_score=2.0),
        _rec("score", False, pred_score=0.4, gold_score=1.0),
    ]
    assert math.isclose(score_mae(records), (0.1 + 0.6) / 2)


def test_latency_percentiles() -> None:
    p50, p95 = latency_percentiles([0.1, 0.2, 0.3, 0.4, 1.0])
    assert p50 == 0.3
    assert p95 == 1.0


def test_summarize_shape_and_nan_cleaning() -> None:
    records = [
        _rec(
            "choice",
            True,
            confidence=0.9,
            pred_probs={"a": 1.0},
            gold_probs={"a": 1.0},
            pred_choice="a",
            gold_choice="a",
        ),
        _rec("noul", False, confidence=0.6, pred_probs={"1": 0.4}, gold_probs={"1": 1.0}),
    ]
    summary = summarize(records, [0.05, 0.07], error_budget=0.05)
    assert summary["n_questions"] == 2
    assert summary["accuracy"] == 0.5
    assert set(summary["by_type"]) == {"choice", "noul"}
    assert "coverage_at_5%_error" in summary
