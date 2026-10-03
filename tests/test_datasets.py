"""Adapter and fixture checks (contracts C5, C6) — fully offline."""

from __future__ import annotations

import json
import math

from decision_bench.datasets.fixture import load_fixtures
from decision_bench.datasets.typed_decisions import _gold_for


def test_fixtures_cover_all_types_with_gold() -> None:
    cases = load_fixtures()
    assert len(cases) >= 8
    seen_types: set[str] = set()
    for case in cases:
        assert case.questions, case.case_id
        for question in case.questions:
            seen_types.add(question.qtype)
            gold = case.gold[question.qid]
            if question.qtype == "choice":
                assert gold.choice is not None
                assert set(gold.probs) == set(question.criteria or {})
            elif question.qtype == "score":
                assert gold.level is not None and gold.score is not None
                assert len(question.criteria) == len(gold.probs)
            else:
                assert 0.0 <= gold.ptrue <= 1.0
    assert seen_types == {"choice", "score", "noul"}
    # extended fixtures (soft golds, contributed by the parallel session) are merged in
    extended = [case for case in cases if case.workflow == "extended"]
    assert len(extended) >= 8
    assert any(case.case_id.endswith("-fr") for case in extended)
    for case in extended:
        for gold in case.gold.values():
            assert math.isclose(sum(gold.probs.values()), 1.0, rel_tol=0.01)


def test_typed_decisions_gold_parsing_choice() -> None:
    gold = _gold_for("choice", {"label": "continue", "probabilities": {"continue": 0.9, "human_review": 0.1}})
    assert gold.choice == "continue"
    assert gold.probs == {"continue": 0.9, "human_review": 0.1}


def test_typed_decisions_gold_parsing_score() -> None:
    gold = _gold_for("score", {"label": "1", "score": 0.79, "probabilities": {"0": 0.4, "1": 0.6}})
    assert gold.level == 1
    assert gold.score == 0.79


def test_typed_decisions_gold_parsing_noul() -> None:
    assert _gold_for("noul", {"label": True}).ptrue == 1.0
    assert _gold_for("noul", {"label": False}).ptrue == 0.0
    assert _gold_for("noul", {"label": 0.3}).ptrue == 0.3
    # dataset quirk: labels also come as the strings "true"/"false"
    assert _gold_for("noul", {"label": "true"}).ptrue == 1.0
    assert _gold_for("noul", {"label": "false"}).ptrue == 0.0


def test_typed_decisions_row_decodes_to_request() -> None:
    """A dataset row (JSON-string columns) must decode into {state, questions} for one request."""
    row = {
        "id": "agent_trace_observability_000000",
        "workflow": "agent_trace_observability",
        "state": json.dumps({"task": "Rotate TLS cert", "agent": {"autonomy": "checkpointed"}}),
        "questions": json.dumps(
            {
                "action": {
                    "type": "choice",
                    "instructions": "What next?",
                    "criteria": {"continue": "proceed", "human_review": "human", "rollback": "undo"},
                },
                "needs_review": {
                    "type": "noul",
                    "instructions": "Needs review?",
                    "criteria": {"false": "no review", "true": "review"},
                },
                "risk": {"type": "score", "instructions": "Risk?", "criteria": ["none", "low", "high"]},
            }
        ),
        "gold": json.dumps(
            {
                "action": {"label": "continue", "probabilities": {"continue": 1.0}},
                "needs_review": {"label": False},
                "risk": {"label": "1", "score": 0.79},
            }
        ),
    }
    questions_raw = json.loads(row["questions"])
    gold_raw = json.loads(row["gold"])
    assert set(questions_raw) == set(gold_raw)
    assert questions_raw["action"]["type"] == "choice"
    assert questions_raw["needs_review"]["criteria"]["false"] == "no review"  # dataset quirk: string keys
    assert _gold_for("score", gold_raw["risk"]).level == 1
