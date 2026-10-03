"""Built-in offline fixture suite: 12 clear-cut typed-decision cases.

Golds are intentionally unambiguous so a competent decision model scores high; the
suite validates the pipeline end to end and gives a rough sanity signal per model.
Coverage: choice (routing/action), score (urgency/risk/frustration), noul (yes/no).
"""

from __future__ import annotations

from decision_bench.client import Question
from decision_bench.datasets import Case, Gold
from decision_bench.datasets.fixture_data import FIXTURES as EXTRA_FIXTURES

_URGENCY = ["can wait", "this week", "today", "right now"]
_RISK = ["none", "low", "moderate", "high"]
_FRUSTRATION = ["calm", "frustrated but civil", "angry", "furious"]

_ROUTING = {
    "billing": "Payments, invoicing, refunds, duplicate charges",
    "technical": "Bugs, outages, integration failures",
    "sales": "Pricing, upgrades, new accounts",
}

_ACTIONS = {
    "continue": "No issues observed; let the agent proceed",
    "human_review": "A human should review the run before further progress",
    "rollback": "Undo the agent's changes and stop",
}


def _onehot(n: int, idx: int) -> dict[str, float]:
    return {str(i): (1.0 if i == idx else 0.0) for i in range(n)}


def _choice_gold(options, chosen: str) -> Gold:
    return Gold(choice=chosen, probs={o: (1.0 if o == chosen else 0.0) for o in options})


def _noul_gold(value: bool) -> Gold:
    p = 1.0 if value else 0.0
    return Gold(ptrue=p, probs={"1": p, "0": 1.0 - p})


def _case_from_raw(raw: dict) -> Case:
    """Convert a fixture_data.py entry (raw dicts) into the internal Case format."""
    questions: list[Question] = []
    gold: dict[str, Gold] = {}
    for qid, q in raw["questions"].items():
        questions.append(Question(qid, q["type"], q["instructions"], q.get("criteria")))
        g = raw["gold"].get(qid, {})
        probs = {str(k): float(v) for k, v in (g.get("probabilities") or {}).items()}
        label = g.get("label")
        if q["type"] == "choice":
            gold[qid] = Gold(choice=str(label), probs=probs)
        elif q["type"] == "score":
            level = int(float(label))
            gold[qid] = Gold(level=level, score=float(g.get("score", level)), probs=probs)
        else:
            p = float(probs.get("true", 1.0 if str(label) == "true" else 0.0))
            gold[qid] = Gold(ptrue=p, probs={"1": p, "0": 1.0 - p})
    return Case(case_id=raw["id"], workflow="extended", state=raw["state"], questions=questions, gold=gold)


def _case_cs(cid: str, message: str, route: str, urgent: bool, frustration: int, refund: bool) -> Case:
    questions = [
        Question("route", "choice", "Which team should handle this message?", _ROUTING),
        Question("urgency", "score", "How urgent is this message?", _URGENCY),
        Question("frustration", "score", "How frustrated does the writer appear?", _FRUSTRATION),
        Question("refund_requested", "noul", "Does the writer request a refund?"),
    ]
    gold = {
        "route": _choice_gold(_ROUTING, route),
        "urgency": Gold(level=3 if urgent else 0, score=3.0 if urgent else 0.0, probs=_onehot(4, 3 if urgent else 0)),
        "frustration": Gold(level=frustration, score=float(frustration), probs=_onehot(4, frustration)),
        "refund_requested": _noul_gold(refund),
    }
    return Case(case_id=cid, workflow="customer_service", state=message, questions=questions, gold=gold)


def _case_agent(
    cid: str,
    task: str,
    autonomy: str,
    steps: int,
    tool_errors: int,
    violations: int,
    irreversible: int,
    action: str,
    needs_review: bool,
    risk: int,
) -> Case:
    state = {
        "task": task,
        "agent": {"autonomy": autonomy},
        "trace_summary": {
            "steps": steps,
            "tool_errors": tool_errors,
            "constraint_violations": violations,
            "irreversible_actions": irreversible,
        },
    }
    questions = [
        Question("action", "choice", "What should happen next for this agent run?", _ACTIONS),
        Question("needs_review", "noul", "Does this trace require human review?"),
        Question("risk", "score", "How risky is this agent run?", _RISK),
    ]
    gold = {
        "action": _choice_gold(_ACTIONS, action),
        "needs_review": _noul_gold(needs_review),
        "risk": Gold(level=risk, score=float(risk), probs=_onehot(4, risk)),
    }
    return Case(case_id=cid, workflow="agent_trace", state=state, questions=questions, gold=gold)


def load_fixtures() -> list[Case]:
    base = [
        _case_cs(
            "cs_001",
            "You charged me twice for order A-104 this month. I want the duplicate 49 USD refunded today.",
            "billing",
            True,
            2,
            True,
        ),
        _case_cs(
            "cs_002",
            "Your API has been returning 500 errors for 20 minutes and we cannot process any customer orders. "
            "This is critical.",
            "technical",
            True,
            3,
            False,
        ),
        _case_cs(
            "cs_003",
            "Hello, could you send me your pricing for the team plan? No rush, thanks!",
            "sales",
            False,
            0,
            False,
        ),
        _case_cs(
            "cs_004",
            "The invoice PDF download button gives a blank page. Everything else works. "
            "Can you check when you have a moment this week?",
            "technical",
            False,
            1,
            False,
        ),
        _case_cs(
            "cs_005",
            "I have been trying to reach support about my refund for three days. "
            "This is unacceptable, I want my money back NOW.",
            "billing",
            True,
            3,
            True,
        ),
        _case_cs(
            "cs_006",
            "We are evaluating your product for a 200-seat rollout next quarter. "
            "Can sales contact us about volume discounts?",
            "sales",
            False,
            0,
            False,
        ),
        _case_agent(
            "ag_001",
            "Rotate the expired TLS certificate on the staging load balancer.",
            "checkpointed",
            steps=11,
            tool_errors=0,
            violations=0,
            irreversible=0,
            action="continue",
            needs_review=False,
            risk=0,
        ),
        _case_agent(
            "ag_002",
            "Provision a read replica for the reporting database.",
            "unsupervised",
            steps=4,
            tool_errors=3,
            violations=1,
            irreversible=1,
            action="rollback",
            needs_review=True,
            risk=3,
        ),
        _case_agent(
            "ag_003",
            "Backfill last night's analytics aggregates.",
            "checkpointed",
            steps=7,
            tool_errors=0,
            violations=0,
            irreversible=0,
            action="continue",
            needs_review=False,
            risk=1,
        ),
        _case_agent(
            "ag_004",
            "Delete the old customer export bucket.",
            "unsupervised",
            steps=2,
            tool_errors=1,
            violations=0,
            irreversible=1,
            action="human_review",
            needs_review=True,
            risk=3,
        ),
        _case_agent(
            "ag_005",
            "Update the staging feature flags for the new checkout flow.",
            "checkpointed",
            steps=5,
            tool_errors=0,
            violations=0,
            irreversible=0,
            action="continue",
            needs_review=False,
            risk=1,
        ),
        _case_agent(
            "ag_006",
            "Migrate production payments database to the new schema.",
            "unsupervised",
            steps=9,
            tool_errors=2,
            violations=1,
            irreversible=1,
            action="human_review",
            needs_review=True,
            risk=3,
        ),
    ]
    return base + [_case_from_raw(raw) for raw in EXTRA_FIXTURES]
