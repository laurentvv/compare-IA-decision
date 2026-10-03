"""Request builder must match the pinned /v1/systemone doc (contract C4)."""

from __future__ import annotations

import pytest

from decision_bench.client import Question, build_request
from decision_bench.mock_server import _answer


def test_request_shape_matches_pinned_doc() -> None:
    request = build_request(
        "Help! My payouts have been failing for 3 days.",
        [
            Question("route", "choice", "Which team?", {"billing": "Payments", "technical": None}),
            Question("angry", "noul", "Is the writer angry?", {"true": "explicit", "false": "none"}),
            Question("urgency", "score", "How urgent?", ["can wait", "today", "right now"]),
        ],
    )
    assert set(request) == {"state", "questions"}
    assert request["questions"]["route"] == {
        "type": "choice",
        "instructions": "Which team?",
        "criteria": {"billing": "Payments", "technical": None},
    }
    assert request["questions"]["angry"]["type"] == "noul"
    assert request["questions"]["urgency"]["criteria"] == ["can wait", "today", "right now"]


def test_invalid_type_rejected() -> None:
    with pytest.raises(ValueError, match="not in"):
        build_request("s", [Question("q", "boolean", "bad type")])


def test_choice_requires_map_criteria() -> None:
    with pytest.raises(ValueError, match="choice criteria"):
        build_request("s", [Question("q", "choice", "bad", ["a", "b"])])


def test_score_requires_list_criteria() -> None:
    with pytest.raises(ValueError, match="score criteria"):
        build_request("s", [Question("q", "score", "bad", {"low": "x"})])


def test_empty_questions_rejected() -> None:
    with pytest.raises(ValueError, match="at least one"):
        build_request("s", [])


def test_mock_answer_shapes() -> None:
    choice = _answer("route", {"type": "choice", "criteria": {"a": "x", "b": "y"}}, "state")
    assert choice["type"] == "choice" and choice["choice"] in {"a", "b"}
    assert abs(sum(choice["probabilities"].values()) - 1.0) < 1e-6
    assert choice["probabilities"].keys() == {"a", "b"}

    score = _answer("urg", {"type": "score", "criteria": ["low", "mid", "high"]}, "state")
    assert set(score["probabilities"]) == {"0", "1", "2"}
    assert score["legend"] == {"0": "low", "1": "mid", "2": "high"}
    assert 0.0 <= score["score"] <= 2.0

    noul = _answer("n", {"type": "noul"}, "state")
    assert 0.0 <= noul["noul"] <= 1.0

    # determinism: same state + qid -> same distribution
    again = _answer("route", {"type": "choice", "criteria": {"a": "x", "b": "y"}}, "state")
    assert again == choice
