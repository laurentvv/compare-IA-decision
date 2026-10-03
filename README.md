# compare-IA-decision

Comparison bench for **System One decision models** served locally by llama.cpp's
`POST /v1/systemone` endpoint (PR
[ggml-org/llama.cpp#29818](https://github.com/ggml-org/llama.cpp/pull/29818), merged
2026-10-02, "TypeSafe-compatible").

Decision models do not generate text: one forward pass reads a `state` and answers typed
questions (`choice`, `score`, `noul`) with probability distributions.

## Models compared (all Q8_0 — matched-weights rule)

| model | base | size (Q8_0) | license | GGUF |
|---|---|---|---|---|
| julia-1 | mmBERT-small, 144M | 168 MB | Apache-2.0 | `ggml-org/Julia-1-GGUF` |
| laya | ModernBERT-large, 421M | 449 MB | Apache-2.0 | `ggml-org/Laya-GGUF` |
| lev | Qwen3.5-4B | 4.5 GB | Apache-2.0 | `ggml-org/lev-GGUF` |
| kev-0.8b | 0.8B | 812 MB | Apache-2.0 | `ggml-org/Kev-0.8B-GGUF` |
| kev-4b | Qwen3.5-4B | 4.8 GB | Apache-2.0 | `ggml-org/Kev-4B-GGUF` |
| openjev (disabled) | Qwen3.5 vision, ~35B-A3B MoE | 28.6 GB | CC-BY-NC-4.0 | `ggml-org/OpenJev-GGUF` |

GGUFs live in `D:/Modeles_LLM/Decision/<Family>/` (paths declared in `configs/bench.toml`).

## Benchmarks

- **`LocalLLaMA/typed-decisions`** — 400 test cases x 5 typed questions across the 4
  TypeSafe workflows (agent-trace observability, customer service, invoice processing,
  security incidents); gold is a full probability distribution, so calibration matters.
- **jev-benchmarks protocol** (AbdelStark/jev-benchmarks, `docs/PROTOCOL.md`) — metric
  suite reused here: accuracy, macro-F1, multiclass Brier, NLL, top-label ECE (10 bins),
  mean KL vs gold, coverage at a fixed error budget, latency p50/p95. Failed requests are
  counted, never retried.
- Pinned upstream docs: `scratch/upstream_docs/` (llama.cpp server README @ master
  `cb7934c5`, Julia-1 card, typed-decisions card, jev-benchmarks).

## Usage

```bash
uv sync

# offline pipeline check (no llama.cpp needed)
uv run decision-bench run --suite fixture --mock

# real run: every enabled model, fixture suite (12 clear-cut cases)
uv run decision-bench run --suite fixture

# real run: 25-case slice of typed-decisions test (downloads the dataset once)
uv run decision-bench run --suite typed-decisions --limit 25

# full typed-decisions test split (400 cases / 2000 decisions per model)
uv run decision-bench run --suite typed-decisions

# single model, or attach to an already-running server
uv run decision-bench run --suite typed-decisions --models julia-1
uv run decision-bench run --suite typed-decisions --base-url http://127.0.0.1:8080

uv run decision-bench validate-config
```

Requires a llama-server build that contains PR #29818 (e.g. `0.5.0-dev build 11370,
commit bed0a8566` or any release after v0.5.0). Server binary and model paths are
configured in `configs/bench.toml` only.

## Outputs

Per run: `results/<timestamp>/<model>__<suite>.json` (per-question records + metrics)
and `results/<timestamp>/summary.md` (comparison table).

## Status

Contract: `contract.md` (frozen). Evidence: `progress.md`. Upstream reference material
on the models themselves: `C:/GIT/jev-ai` (TypeSafe/Jev dossier) and `C:/GIT/Laya`.
