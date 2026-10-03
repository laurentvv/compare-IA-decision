"""Benchmark suites: built-in fixtures (offline) and LocalLLaMA/typed-decisions (public)."""

from __future__ import annotations

from dataclasses import dataclass, field

from decision_bench.client import Question

SUITES = ("fixture", "typed-decisions")


@dataclass
class Gold:
    choice: str | None = None
    level: int | None = None
    score: float | None = None
    ptrue: float | None = None
    probs: dict[str, float] = field(default_factory=dict)


@dataclass
class Case:
    case_id: str
    workflow: str
    state: object  # str or JSON-serializable object
    questions: list[Question]
    gold: dict[str, Gold]


def load_suite(
    name: str,
    limit: int | None = None,
    dataset_config: str = "all",
    split: str = "test",
) -> list[Case]:
    if name == "fixture":
        from decision_bench.datasets.fixture import load_fixtures

        cases = load_fixtures()
    elif name == "typed-decisions":
        from decision_bench.datasets.typed_decisions import load_typed_decisions

        cases = load_typed_decisions(config_name=dataset_config, split=split)
    else:
        raise ValueError(f"unknown suite {name!r}; expected one of {SUITES}")
    return cases[:limit] if limit else cases
