# Validation Contract — Decision Models Comparison Bench

Sprint goal: compare the five System One decision models (laya, julia-1, lev, openjev, kev)
served by llama.cpp `POST /v1/systemone` (PR #29818) on typed-decision benchmarks.
Scope: ONLY the comparison bench (client, server manager, mock backend, dataset adapters,
metrics, report). Frozen before the first line of code.
Comparability rule (user decision): all models benchmarked at the SAME quantization (Q8_0).

## Automated Acceptance Criteria

- [ ] C1: `uv run decision-bench --help` exits 0 and documents subcommands `run` and `validate-config`.
- [ ] C2: `uv run ruff check src tests` exits 0 (project gate §3).
- [ ] C3: `uv run pytest` exits 0, all tests green, no network access required by tests.
- [ ] C4: Request builder emits exactly `{state, questions}` with `question.type ∈ {choice, score, noul}`
      matching the pinned API doc (scratch/upstream_docs/llama-cpp/server-README_master_cb7934c.md);
      unit test asserts the JSON shape.
- [ ] C5: typed-decisions adapter parses parquet rows (JSON-string columns) into ONE request per case
      containing all 5 questions and recovers gold: action/outcome (choice), needs_review (noul),
      risk/urgency (score), per dataset card guidance (scratch/upstream_docs/models/typed-decisions_card.md).
- [ ] C6: At least 8 built-in fixture cases ship in-repo covering choice, score and noul with gold answers.
- [ ] C7: Metrics implemented and unit-tested against hand-computed values: accuracy, macro-F1,
      multiclass Brier, NLL (log loss), top-label ECE (10 equal-width bins), mean KL vs gold
      distributions, coverage at 5% error budget, latency p50/p95.
- [ ] C8: Grading rules implemented: choice = argmax vs gold label; score = round(expected score)
      vs gold level plus MAE vs gold continuous score; noul = p(true) ≥ 0.5 vs gold boolean.
- [ ] C9: Full pipeline runs E2E against the bundled mock `/v1/systemone` backend on the fixture
      suite: exit 0, per-model JSON + summary.md produced under results/.
- [ ] C10: Same pipeline runs on a 25-case slice of LocalLLaMA/typed-decisions test (config `all`)
      against the mock backend, producing per-question-type metrics (offline copy of the slice in tests).
- [ ] C11: Report contains per-model × per-question-type rows (accuracy/Brier/NLL/ECE/KL/coverage)
      and p50/p95 latency per model.
- [ ] C12: Server manager starts the configured server binary, polls /health until 200, runs requests,
      then terminates it cleanly; validated against the real local llama-server.
- [ ] C13: Failed requests are counted, kept in the denominator and reported; no silent retry
      (jev-benchmarks protocol rule).
- [ ] C14: No hardcoded machine paths in code: model/server paths come from configs/bench.toml,
      overridable via CLI flags.
- [ ] C15: No secrets in code or logs; the bench only talks to localhost HTTP; dataset download from
      huggingface.co is explicit and cached.
- [ ] C16: Real E2E: bench runs against the local llama-server (0.5.0-dev build ≥ 11370, commit
      bed0a8566, with PR #29818) for every enabled model on the fixture suite AND a 25-case
      typed-decisions slice; exit 0; reports under results/.

## Evaluation Protocol

* Commands:
  - `uv run ruff check src tests`
  - `uv run pytest`
  - `uv run decision-bench run --config configs/bench.toml --suite fixture`
  - `uv run decision-bench run --config configs/bench.toml --suite typed-decisions --limit 25`
  - Offline equivalent of the two run commands with `--mock`.
* Expected: all exit 0; key numbers copied into progress.md as evidence.
* Out of scope / deferred: OpenJev run by default (35B-A3B MoE, 28.6 GB Q8_0, CC-BY-NC-4.0,
  exceeds the <8B target — kept `enabled = false` in config); vision/mmproj path; hosted TypeSafe
  API comparison; cross-quantization comparison (user locked Q8_0 only).
