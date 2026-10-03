"""CLI: `decision-bench run` and `decision-bench validate-config`."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from decision_bench import __version__
from decision_bench.config import load_config, select_models
from decision_bench.datasets import SUITES, load_suite
from decision_bench.report import print_table, write_summary_md
from decision_bench.runner import run_model


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", type=Path, default=Path("configs/bench.toml"), help="TOML config path")
    parser.add_argument("--models", default=None, help="comma-separated model names (default: all enabled)")
    parser.add_argument("--output", type=Path, default=None, help="override output directory")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="decision-bench", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="run a benchmark suite against the configured models")
    _add_common(run_p)
    run_p.add_argument("--suite", choices=SUITES, default="fixture")
    run_p.add_argument("--limit", type=int, default=None, help="cap the number of cases")
    run_p.add_argument("--dataset-config", default="all", help="typed-decisions config (default: all)")
    run_p.add_argument("--split", default="test", help="typed-decisions split (default: test)")
    run_p.add_argument("--base-url", default=None, help="attach to an already-running /v1/systemone server")
    run_p.add_argument("--mock", action="store_true", help="use the bundled deterministic mock backend")

    cfg_p = sub.add_parser("validate-config", help="load the TOML config and print the resolved models")
    _add_common(cfg_p)

    args = parser.parse_args(argv)
    try:
        cfg = load_config(args.config)
    except (OSError, ValueError, KeyError) as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2

    if args.command == "validate-config":
        for model in cfg.models:
            state = "enabled " if model.enabled else "disabled"
            print(f"{model.name:<12} {state} {model.gguf_path} {' '.join(model.extra_args)}".rstrip())
        print(f"server: binary={cfg.server.binary or '<unset>'} {cfg.server.host}:{cfg.server.port}")
        return 0

    only = args.models.split(",") if args.models else None
    try:
        models = select_models(cfg, only)
        cases = load_suite(args.suite, limit=args.limit, dataset_config=args.dataset_config, split=args.split)
    except (ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    output_dir = args.output or cfg.output_dir
    run_dir = output_dir / time.strftime("%Y%m%d_%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)

    backend = "mock" if args.mock else args.base_url or "llama-server"
    print(f"suite={args.suite} cases={len(cases)} models={[m.name for m in models]} backend={backend}")
    runs = []
    for model in models:
        print(f"running {model.name} ...", flush=True)
        runs.append(run_model(cfg, model, args.suite, cases, run_dir, base_url=args.base_url, mock=args.mock))

    summary_path = write_summary_md(runs, args.suite, len(cases), cfg.error_budget, run_dir)
    print(print_table(runs))
    print(f"\nreports: {summary_path}")
    ok_runs = [r for r in runs if not r.error]
    healthy = ok_runs and all(
        r.summary.get("n_questions", 0) > r.summary.get("failures", 1) for r in ok_runs
    )
    return 0 if healthy else 1


if __name__ == "__main__":
    sys.exit(main())
