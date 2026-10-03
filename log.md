# Execution Log (Append-Only)

## [2026-10-03] init | agents-kit instantiation (AGENTS.md template).
## [2026-10-03] gen  | Models identified via llama.cpp PR #29818; upstream docs pinned in scratch/; benchmarks: typed-decisions + jev-benchmarks.
## [2026-10-03] gen  | Contract frozen; Q8_0 GGUF downloads to D:/Modeles_LLM/Decision (bg); local llama-server b11370 already has /v1/systemone.
## [2026-10-03] gen  | F-03: implementing decision_bench package (api/grading/metrics/datasets/config/server/mock/runner/report/cli) + tests + configs on feat/bench.
## [2026-10-03] fix  | Kev-4B corrupted by curl -C - resume across HF redirect (5.3 GB vs 4.48 GB expected): fresh download + sha256 7c2ebed9 OK. Corrupt OpenJev partial removed (disabled model).
## [2026-10-03] eval | Real E2E exposed encoder ubatch limit: julia-1 GGML_ASSERT at case 19 (30/125 questions lost) -> --ubatch-size 8192 for julia-1/laya (pinned README rule), -ngl 99 for 4B models (CPU 4.5 min/suite too slow).
## [2026-10-03] done | F-02/F-03/F-04 complete: 26 tests green, mock E2E ok, real E2E both suites 0 failures (fixture 51 s, typed-25 94 s). Evidence in progress.md; features archived.
