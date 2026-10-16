# Sprint Progress

## Current Goal
- [ ] Compare the five System One decision models (laya, julia-1, lev, openjev, kev) via llama.cpp
  `POST /v1/systemone` on typed-decision benchmarks, at identical quantization (Q8_0).

## Iteration Milestones
- [x] Models identified: PR #29818 (merged 2026-10-02) confirms laya, julia-1, lev, openjev, kev;
  ggml-org GGUF repos listed; benchmarks found: `LocalLLaMA/typed-decisions` (400 test cases x 5
  typed questions) + `AbdelStark/jev-benchmarks` protocol (accuracy/macro-F1/Brier/NLL/ECE/
  coverage@5%/latency).
- [x] Upstream docs pinned in scratch/upstream_docs/ (llama.cpp master cb7934c5 server README,
  Julia-1 card, typed-decisions card, jev-benchmarks README+PROTOCOL).
- [x] Local llama-server 0.5.0-dev build 11370 (bed0a8566) at C:/llama.cpp already supports
  /v1/systemone (independent smoke on Julia-1 logged by user's monitoring setup).
- [x] Contract frozen before first line of code.
- [x] Q8_0 GGUFs downloaded to D:/Modeles_LLM/Decision/ (julia-1 168 MB, laya 449 MB, lev 4.48 GB, kev-0.8b 812 MB, kev-4b 4.48 GB sha256-verified; openjev kept disabled, corrupt partial removed).
- [x] Bench implemented and validated (contract C1-C16, evidence below).

## Contract Validation (2026-10-03, llama-server 0.5.0-dev build 11370 / bed0a8566)

| Crit | Evidence | Result |
|---|---|---|
| C1 | `uv run decision-bench --help` | exit 0, subcommands `run` + `validate-config` |
| C2 | `uv run ruff check src tests` | "All checks passed!" |
| C3 | `uv run pytest` | **26 passed**, offline |
| C4 | tests/test_request_and_mock.py | exact `{state, questions}` shape vs pinned server README |
| C5 | tests/test_datasets.py | JSON-string columns -> ONE request/case, gold recovered (incl. string-noul quirk) |
| C6 | datasets/fixture.py | 12 clear-cut cases + extended soft-gold cases, all 3 types with gold |
| C7 | tests/test_metrics.py | accuracy/macro-F1/Brier(sum)/NLL/ECE10/KL/coverage/percentiles hand-computed |
| C8 | runner.grade_case + metric tests | choice=argmax, score=round-half-up+MAE, noul=p>=0.5 |
| C9 | `run --suite fixture --mock` / `--suite typed-decisions --limit 25 --mock` | exit 0, per-model JSON + summary.md (results/20261003_1100*, _110212) |
| C10 | mock 25-case slice (tests/data/typed_decisions_slice.parquet) + real run | per-type metrics produced |
| C11 | results/*/summary.md | per-model x per-type acc/F1/Brier/NLL/ECE/KL/coverage + p50/p95 |
| C12 | LlamaServerManager all real runs | start -> /health 200 -> requests -> clean stop, per model |
| C13 | first real typed-decisions run | julia-1 server abort -> 30/125 failures COUNTED and reported (fixed via --ubatch-size, rerun 0 fails) |
| C14 | configs/bench.toml + --models/--output/--base-url | no machine paths in code |
| C15 | client localhost-only; dataset via huggingface_hub cached snapshot | no secrets, no silent network in tests |
| C16 | real E2E both suites, 5 enabled models | fixture 12 cases: 51 s, **0 failures** (results/20261003_112226); typed-decisions 25 cases: 94 s, **0 failures** (results/20261003_111958) |

### Key numbers — typed-decisions test slice (25 cases, 125 questions/model, Q8_0, llama-server)

| model | acc | choice | score | noul | Brier | NLL | ECE10 | KL | cov@5% | p50 s |
|---|---|---|---|---|---|---|---|---|---|---|
| julia-1 | **0.672** | 0.600 | **0.620** | **0.920** | 0.416 | 4.500 | 0.303 | 3.727 | 0.008 | 0.030 |
| lev | 0.584 | **0.680** | 0.340 | 0.880 | 0.150 | 1.062 | 0.124 | **0.289** | 0.032 | 1.042 |
| laya | 0.472 | 0.420 | 0.420 | 0.680 | 0.282 | 1.295 | **0.108** | 0.521 | 0.016 | 0.072 |
| kev-4b | 0.432 | 0.520 | 0.260 | 0.600 | 0.194 | 1.127 | 0.126 | 0.353 | **0.040** | 0.669 |
| kev-0.8b | 0.352 | 0.360 | 0.280 | 0.480 | 0.247 | 1.216 | 0.158 | 0.443 | 0.008 | 0.398 |

Dataset reference: Prior accuracy 0.470. Fixtures (clear-cut, 12 cases): kev-4b 0.727 > lev 0.682 >
laya 0.530 > kev-0.8b 0.500 > julia-1 0.379.

Reading: julia-1 wins accuracy and latency but is badly calibrated on this slice (KL 3.7, NLL 4.5);
lev is the best all-rounder (accuracy x KL); laya is the best-calibrated; kev-4b wins on clear-cut
fixtures and selective automation (cov@5%) but sits under the dataset prior on accuracy. Full
distributions per model in results/<ts>/<model>__<suite>.json.

## Final full run — post-reconciliation clean rerun (2026-10-03 09:28-09:45 UTC, exit 0)

After merging the parallel session's work: identity check via `GET /props` `model_path`,
2 s settle after load (excluded from latency), `--ubatch-size 8192` on encoders,
`-ngl 99` on 4B models. **0 failures over 10 000 decisions** (2 000 x 5 models).

Fixture (20 cases): kev-4b 0.727 > lev 0.682 > laya 0.530 > kev-0.8b 0.500 > julia-1 0.379;
kev-4b noul 0.950; julia-1 noul 0.500.

typed-decisions FULL (400 cases, 2 000 decisions/model):

| model | acc | Brier | NLL | ECE10 | KL | cov@5% | p50 s | mean case | load s |
|---|---|---|---|---|---|---|---|---|---|
| julia-1 | **0.725** | 0.381 | 3.441 | 0.227 | 2.810 | 0.001 | **0.053** | 55 ms | 1.2 |
| kev-4b | 0.630 | **0.195** | **0.966** | 0.153 | **0.335** | **0.069** | 0.863 | 850 ms | 4.7 |
| lev | 0.588 | 0.218 | 1.013 | **0.087** | 0.382 | 0.042 | 1.100 | 1 136 ms | 4.2 |
| kev-0.8b | 0.429 | 0.277 | 1.106 | 0.152 | 0.475 | 0.019 | 0.603 | 582 ms | 2.2 |
| laya | 0.340 | 0.399 | 1.324 | 0.112 | 0.693 | 0.000 | 0.152 | 141 ms | 0.7 |

Refs: prior 0.470, teacher ceiling 0.735. Full tables + reading in
docs/System-One-Decision-Models-Bench-Report-2026-10-03.md; raw summaries in docs/runs/.
