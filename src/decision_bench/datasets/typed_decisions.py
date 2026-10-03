"""Adapter for the LocalLLaMA/typed-decisions benchmark dataset.

Schema (dataset card pinned in scratch/upstream_docs/models/typed-decisions_card.md):
per row `id, workflow, split, state, questions, gold, factors, label_agreement,
n_questions`, where state/questions/gold are JSON-encoded strings. Five questions per
case (action: choice, needs_review: noul, outcome: choice, risk: score, urgency: score).
Guidance honored: the whole case is sent as ONE request; gold distributions are kept
for calibration metrics (KL/Brier), since "calibration is the point".
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from decision_bench.client import Question
from decision_bench.datasets import Case, Gold

logger = logging.getLogger(__name__)

_DATASET_ID = "LocalLLaMA/typed-decisions"
_REPO_ROOT = Path(__file__).resolve().parents[3]


def _download_snapshot() -> Path:
    from huggingface_hub import snapshot_download

    return Path(snapshot_download(DATASET_ID, repo_type="dataset"))


def _dataset_root() -> Path:
    """Prefer the committed offline copy (data/typed-decisions), else the HF hub snapshot."""
    local = _REPO_ROOT / "data" / "typed-decisions"
    if local.is_dir() and any(local.glob("*.parquet")):
        return local
    return _download_snapshot()


def _select_parquets(root: Path, config_name: str, split: str) -> list[Path]:
    parquets = sorted(root.rglob("*.parquet"))
    if not parquets:
        raise FileNotFoundError(f"no parquet files found in {DATASET_ID} snapshot at {root}")
    in_config = [p for p in parquets if config_name in p.parts]
    with_split = [p for p in in_config if split in p.stem]
    if with_split:
        return with_split
    if in_config and config_name != "all":
        return in_config
    # 'all' config missing: fall back to every per-workflow split file
    per_split = [p for p in parquets if split in p.stem and "all" not in p.parts]
    return per_split or parquets


def _gold_for(qtype: str, raw: dict) -> Gold:
    probs = {str(k): float(v) for k, v in (raw.get("probabilities") or {}).items()}
    label = raw.get("label")
    if qtype == "choice":
        return Gold(choice=None if label is None else str(label), probs=probs)
    if qtype == "score":
        level = int(float(label))
        score = float(raw["score"]) if "score" in raw else float(level)
        return Gold(level=level, score=score, probs=probs)
    if isinstance(label, bool):
        ptrue = 1.0 if label else 0.0
    elif isinstance(label, str):
        # dataset quirk: noul labels also come as the strings "true"/"false"
        ptrue = 1.0 if label.lower() == "true" else 0.0
    else:
        ptrue = float(label)
    return Gold(ptrue=ptrue, probs={"1": ptrue, "0": 1.0 - ptrue})


def load_typed_decisions(config_name: str = "all", split: str = "test") -> list[Case]:
    import pandas as pd

    root = _dataset_root()
    paths = _select_parquets(root, config_name, split)
    logger.info("typed-decisions: reading %s", ", ".join(p.name for p in paths))
    cases: list[Case] = []
    seen: set[str] = set()
    for path in paths:
        frame = pd.read_parquet(path)
        for row in frame.to_dict("records"):
            case_id = str(row["id"])
            if case_id in seen:  # 'all' config can overlap per-workflow files
                continue
            seen.add(case_id)
            questions_raw = json.loads(row["questions"])
            gold_raw = json.loads(row["gold"])
            questions: list[Question] = []
            gold: dict[str, Gold] = {}
            for qid, q in questions_raw.items():
                questions.append(
                    Question(
                        qid=qid,
                        qtype=q["type"],
                        instructions=q["instructions"],
                        criteria=q.get("criteria"),
                    )
                )
                gold[qid] = _gold_for(q["type"], gold_raw.get(qid, {}))
            cases.append(
                Case(
                    case_id=case_id,
                    workflow=str(row.get("workflow", "unknown")),
                    state=json.loads(row["state"]),
                    questions=questions,
                    gold=gold,
                )
            )
    return cases
