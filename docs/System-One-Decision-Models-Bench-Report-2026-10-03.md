# System One Decision Models — Field Report, Local Bench & Benchmarks (2026-10-03)

> Dossier compiled for the compare-IA-decision project (and reusable as video research
> material). Everything in §7 is **measured locally on 2026-10-03** with the bench in this
> repository; everything else is sourced from upstream docs pinned in
> `scratch/upstream_docs/` and the local dossiers `C:/GIT/jev-ai` and `C:/GIT/Laya`.

---

## 0. TL;DR

- "System One" decision models answer **typed questions** (`choice`, `score`, `noul`)
  about a `state` with **calibrated probability distributions** — no text generation, no
  chain-of-thought, **one forward pass** (Kahneman's fast/automatic "System 1" vs the slow
  "System 2" of generative LLMs).
- Five open models are officially supported by llama.cpp since PR
  [#29818](https://github.com/ggml-org/llama.cpp/pull/29818) (merged 2026-10-02, highlight):
  **laya** (421M, multilingual guardrails), **julia-1** (144M, routing), **lev** (4B,
  zero-shot classification), **kev** (0.8B / 4B, yes-no judge), **openjev** (~35B-A3B MoE,
  vision, CC-BY-NC).
- Locally they run through `llama-server` and a new **`POST /v1/systemone`** endpoint
  (TypeSafe-compatible). Release v0.5.0 (2026-09-23) does **not** include it; we use a
  dev build (`0.5.0-dev build 11370, commit bed0a8566`) that does.
- Benchmarks to compare them: **`LocalLLaMA/typed-decisions`** (public, 400 test cases ×
  5 typed questions across the 4 TypeSafe workflows) scored with the **jev-benchmarks
  protocol** (accuracy, macro-F1, Brier, NLL, top-label ECE, KL vs gold, coverage at an
  error budget, latency p50/p95). This repo implements exactly that (`decision-bench`).
- Our measured results (all models at **matched Q8_0 quantization**, CPU inference):
  see §7.

## 1. What a "System One" decision model is

| | Generative LLM ("System 2") | Decision model ("System 1") |
|---|---|---|
| Output | generated text, parsed afterwards | probability distribution over a closed schema |
| Latency | 500 ms – 300 s | 3 ms – 500 ms (local: see §7) |
| Schema errors | possible (JSON drift, hallucinated keys) | structurally impossible (closed output space) |
| Calibration | over-confident by default (cross-entropy training) | trained with strictly proper scoring rules (RLCD) |
| Cost | input + output tokens | input tokens only (hosted reference: $0.042 / 1M) |

Three primitives (identical across the TypeSafe API and llama.cpp's implementation):

- **`choice`** — one option among 2–255 with per-option probabilities + `confidence`;
- **`score`** — position on an ordered rubric you describe in natural language
  (probability-weighted expected value, can fall between levels);
- **`noul`** — boolean; returns P(true).

All questions about the same state are evaluated **in parallel in one request**
(adding questions barely moves latency) — the request shape is
`{"state": ..., "questions": {"<id>": {...}}}` and answers come back under the same ids.

## 2. The five open models (all pre-converted by ggml-org)

| model | base architecture | params | file used (Q8_0) | size | license | GGUF repo |
|---|---|---|---|---|---|---|
| **julia-1** | mmBERT-small (ModernBERT) | 144.3M | `Julia-1-Q8_0.gguf` | 168 MB | Apache-2.0 | `ggml-org/Julia-1-GGUF` |
| **laya** | ModernBERT-large | 421M | `Laya-Q8_0.gguf` | 449 MB | Apache-2.0 | `ggml-org/Laya-GGUF` |
| **lev** | Qwen3.5-4B | 4B | `lev-Q8_0.gguf` | 4.48 GB | Apache-2.0 | `ggml-org/lev-GGUF` |
| **kev-0.8b** | 0.8B | 0.8B | `Kev-0.8B-Q8_0.gguf` | 812 MB | Apache-2.0 | `ggml-org/Kev-0.8B-GGUF` |
| **kev-4b** | Qwen3.5-4B | 4B | `Kev-4B-Q8_0.gguf` | 4.78 GB | Apache-2.0 | `ggml-org/Kev-4B-GGUF` |
| **openjev** (optional) | Qwen3.5 vision, MoE | ~35B (A3B active) | `OpenJev-Q8_0.gguf` | 28.6 GB | **CC-BY-NC-4.0** | `ggml-org/OpenJev-GGUF` |

Profiles (from the model cards and the local `jev-ai` / `Laya` dossiers):

- **julia-1** — multilingual routing/classification; the ultra-light CPU option.
  Self-reported (H200 BF16): typed-decisions 73.15 %, AG News 94 %, DAIR Emotion 86 %,
  MASSIVE 71.5 % over 52 locales; known weakness on wide label sets (Banking77 pilot 64 %).
- **laya** — positioned for guardrails/moderation and multilingual triage; trained with
  **RLCD** (strictly proper scoring rules: logarithmic, spherical, RPS) and an
  **Act-vs-Escalate head** (+1 correct automation, −3 confident error, −0.5 escalation →
  automates only above P(correct) > 0.625). Reported ECE 0.081 vs hosted-Jev 0.246;
  ~33–38 ms/question on a Tesla T4. Note: zero-shot base checkpoints are near chance —
  the value is in the specialized fine-tune.
- **lev** — zero-shot classification calibrated (Qwen3.5-4B + LoRA).
- **kev** — trained on banking/boolq/Aegis-safety-style data; the "yes/no judge" profile;
  exists in 0.8B / 4B / 9B.
- **openjev** — vision-capable (screenshots/web pages for browser agents; up to 52
  options per choice) but **non-commercial license** and too big for a 16 GB GPU → kept
  `enabled = false` in `configs/bench.toml`.

## 3. llama.cpp integration — `POST /v1/systemone`

- **PR** [#29818](https://github.com/ggml-org/llama.cpp/pull/29818) —
  "llama, server: add /v1/systemone API (models: laya, julia-1, lev, openjev, kev)",
  merged **2026-10-02**, label *highlight*, +2 139/−15 lines, 35 files. Design: decision
  models are "fancy wrappers around traditional embedding models (BERT/Qwen/etc.)"; the
  server switches behavior on the GGUF metadata `{arch}.decision.type` and routes the
  decision head over the embeddings output (log line: `decision model type: laya`,
  embeddings mode, 4 slots).
- **Release status**: first release containing it is **after v0.5.0** (v0.5.0 is
  2026-09-23, before the merge). Local build used here: `0.5.0-dev build 11370,
  commit bed0a8566` (`C:/llama.cpp`).
- **Request** (exact shape, validated by our client against the pinned README):
  `{state: string|object|array, questions: {id: {type, instructions, criteria}}}` —
  `criteria` is a map `option → description` for `choice`, an ordered array of 2–10
  level descriptions for `score`, and an optional `{"true": ..., "false": ...}` for
  `noul`. Non-string states are passed to the model as JSON text.
- **Response**: `answers[id]` with `choice`+`probabilities`+`confidence` /
  `score`+`legend`+`probabilities`+`confidence` / `noul` probability; `usage.input_tokens`
  (output always 0). Errors: HTTP 400 on invalid requests; non-decision models refuse the
  endpoint.
- **Limits & practical notes**: no streaming; option caps per model (52 for openjev,
  255 for laya); for laya the whole prompt must fit `--ubatch-size`; long
  questions/options are truncated to the trained token budget; probabilities are scaled
  with **temperatures stored in the model file and are not guaranteed calibrated for your
  data** (→ measure Brier/NLL/ECE, don't trust raw confidence); the server default port
  will move to **:9931** in a future release (we pin 8080; range 8871-8970 is Hyper-V
  reserved on this machine); `--mmproj` enables the vision path (openjev).
- **Upstream parity** (PR test table, reference vs llama.cpp probabilities): worst diff
  8.4e-4 (laya), up to 2.2e-2 (julia-1) — close enough for benchmarking.

## 4. The hosted reference: TypeSafe Jev (public figures)

From the official evals (compiled in `C:/GIT/jev-ai/3. Benchmarks chiffrés.md`):
711 business cases across 4 workflows (security incidents 240, agent-trace observability
117, invoice processing 150, customer support 204); agreement with frontier LLMs:
**Jev 67.8 %** vs GPT-5.6 Terra 67.9 %, Claude Opus 5 73.1 %, GPT-5.6 Sol 74.1 %,
Claude Haiku 4.5 58.2 % — at **$0.0004/case** and ~0.4 s (vs $0.03–0.18 and 10–38 s for
the frontier models). JSON schema errors 0 % (Haiku 4.5: 45.5 %). Ground truth = mean of
GPT-6 Astra + Claude Fable 5.1 predictions, scored through the open **System One
Adapter** for autoregressive LLMs. Known failure modes (jev-1.13 docs): literal
instruction reading, no arithmetic/counting, no temporal reasoning, noisy-state
sensitivity, prompt injection through the state, forced choice when no option fits.

## 5. Laya architecture deep-dive (from `C:/GIT/Laya/docs`)

ModernBERT-large backbone (421M total / 395M backbone, 28 layers, 16 heads, GeGLU MLP,
8 192-token RoPE context); **Option Marker Scoring**: a `[MASK]` marker per option, the
decision head (2-layer MLP, 25.2M) gathers those hidden states (1024-d) and softmaxes
them — the output space is closed by construction. Training: **RLCD** with strictly
proper scoring rules (log/spherical/RPS) + TD(λ=1.0) credit assignment on multi-turn
trajectories. **Context bifurcation**: the token budget splits between document
(`max_len`) and options (`head_max_len`); wide taxonomies collapse per-option budget
(Banking77: 77 labels → accuracy ceiling ≈ 42.5 % — use hierarchical routing /
shortlisting above ~20 options). Production calibration: local temperature fitting
brought ECE from 0.466 to 0.081.

## 6. Benchmarks landscape (what to use to compare decision models)

| benchmark / dataset | scale | what it gives |
|---|---|---|
| **`LocalLLaMA/typed-decisions`** (Apache-2.0) | 400 test cases × 5 questions (2 000 decisions); train 1 200 | THE public typed-decisions benchmark; noul/choice/score gold **distributions**; 4 workflows mirroring TypeSafe's internal evals (agent-trace, customer service, invoice, security) |
| **`AbdelStark/jev-benchmarks`** (Apache-2.0) | protocol + pilot (300 ex.) | metric suite: accuracy, macro-F1, multiclass Brier, NLL, top-label ECE (10 bins), coverage @ error budget, p50/p95 latency; paired bootstrap CIs; failure policy (no silent retries) |
| `tasksource/tasksource-jev-typed-decisions` | 2.5M decisions, 670 sources | large-scale training/eval pool |
| `Hanno-Labs/decision-bench` (+ `-results`) | applied domains | "canonical" typed-decision bench across domains |
| `SamuelChien821/typed-decision-bench` | 5 387 items, 25 tasks | contamination tiers (clean/contaminated splits) |
| `tasksource/procedural-typed-decisions` | procedural | exactly computable answers |
| `pngwn/typed-decisions-v2-system-one`, `pngwn/system-one-decisions` | — | System-One request-shape variants |

Reference scores on `typed-decisions` (from the dataset card): Prior floor **0.470**
accuracy / ECE 0.088 (ECE alone is misleading — an input-ignoring prior looks
calibrated); perfect factor recovery 0.704; teacher self-agreement ceiling **0.735**
(gold = mean of three ~4B-class teacher samples; scoring above ≈0.735 means learning
teacher quirks); leaderboard: meraGPT Decider 1 **0.768** acc / KL 0.096 (zero-shot
general), OpenDecider-large-td 0.801 (fitted — separate table). Guidance: send the whole
case in ONE request (per-question requests shifted noul accuracy 0.788 → 0.843); report
KL/log-loss and Brier next to accuracy — "calibration is the point".

jev-benchmarks BTZSC pilot (Jev hosted vs GLiNER2.5 local, 100 ex/condition):
AG News 0.910 vs 0.700 accuracy (coverage@5 % 0.830 vs 0.240); Banking77 0.870 vs 0.610;
DAIR Emotion statistically unresolved (Jev badly calibrated: Brier 0.846 vs 0.668).

## 7. Our local bench — setup and measured results (2026-10-03)

**Machine**: Windows 11, 16 CPU threads, 31.8 GB RAM, GPU AMD Radeon RX 6950 XT 16 GB
(run in CPU mode for this bench), llama-server `0.5.0-dev build 11370 (bed0a8566)`.
**Protocol**: all five models at matched **Q8_0** quantization; one `llama-server` per
model on 127.0.0.1:8080; whole case in ONE `/v1/systemone` request; warmup excluded from
latency; failed requests counted, never retried.
**Suites**: `fixture` (20 clear-cut typed cases, 68 questions) and
**`typed-decisions` full test split (400 cases, 2 000 decisions per model)**.
Raw outputs: `results/<timestamp>/` (per-model JSON with every per-question record).

### 7.1 Fixture suite (20 clear-cut cases, 68 questions) — measured 2026-10-03 09:28 UTC

Raw: `results/20261003_112846/` — **0 failures**; total wall time ≈ 1 min for the 5 models.

| model | acc | choice | score | noul | F1 | Brier | NLL | ECE10 | KL | cov@5% | p50 s | p95 s | tok/case | GB | load s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| kev-4b | **0.727** | 0.750 | 0.538 | **0.950** | 0.550 | **0.237** | **0.677** | 0.180 | 0.424 | **0.515** | 0.390 | 0.451 | 225 | 4.48 | 4.7 |
| lev | 0.682 | **0.800** | 0.462 | 0.850 | **0.752** | 0.277 | 0.746 | 0.139 | 0.493 | 0.409 | 0.551 | 0.652 | 695 | 4.48 | 4.7 |
| laya | 0.530 | 0.600 | 0.346 | 0.700 | 0.482 | 0.502 | 1.133 | 0.168 | 0.880 | 0.106 | **0.030** | **0.038** | 266 | 0.45 | 0.7 |
| kev-0.8b | 0.500 | 0.600 | 0.231 | 0.750 | 0.304 | 0.337 | 0.830 | **0.135** | 0.577 | 0.242 | 0.166 | 0.174 | 225 | 0.81 | 2.2 |
| julia-1 | 0.379 | 0.450 | 0.231 | 0.500 | 0.359 | 0.816 | 2.662 | 0.412 | 2.409 | 0.045 | 0.012 | 0.044 | 228 | 0.17 | **1.2** |

On unambiguous cases **kev-4b is the reliable yes/no judge** (noul 0.950) and lev the best
router (choice 0.800, F1 0.752). julia-1 is fast and tiny but badly calibrated here
(Brier 0.816, noul at chance).

### 7.2 `typed-decisions` full test split (400 cases, 2 000 decisions per model) — measured 2026-10-03 09:29 UTC

Raw: `results/20261003_112938/` — **0 failures** (2 000 requests per model, 10 000 total);
~560 k–985 k input tokens per model; whole case in one request, as the dataset card requires.

| model | acc | choice | score | noul | F1 | Brier | NLL | ECE10 | KL | cov@5% | p50 s | p95 s | tok/case |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| julia-1 | **0.725** | 0.710 | **0.679** | **0.800** | **0.575** | 0.381 | 3.441 | 0.227 | 2.810 | 0.001 | **0.053** | **0.076** | 1 459 |
| kev-4b | 0.630 | 0.642 | 0.530 | 0.753 | 0.440 | **0.195** | **0.966** | 0.153 | **0.335** | **0.069** | 0.863 | 1.074 | 1 405 |
| lev | 0.588 | 0.617 | 0.439 | 0.758 | 0.467 | 0.218 | 1.013 | **0.087** | 0.382 | 0.042 | 1.100 | 1.475 | 2 464 |
| kev-0.8b | 0.429 | 0.508 | 0.295 | 0.530 | 0.338 | 0.277 | 1.106 | 0.152 | 0.475 | 0.019 | 0.603 | 0.800 | 1 405 |
| laya | 0.340 | 0.287 | 0.273 | 0.483 | 0.179 | 0.399 | 1.324 | 0.112 | 0.693 | 0.000 | 0.152 | 0.210 | 1 450 |

Reference points from the dataset card: **Prior floor 0.470** · perfect-factor recovery
0.704 · **teacher self-agreement ceiling 0.735** · leaderboard (zero-shot general):
meraGPT Decider 1 at 0.768 / KL 0.096.

Headlines (all measured, Q8_0, CPU/GPU mix on one desktop):

1. **julia-1 — 144 million parameters, 168 MB — posts 0.725 accuracy at 53 ms/case**,
   within 0.01 of the teacher ceiling and on par with the public leaderboard's leader.
   Caveat: this is its home turf (typed-decisions-specialist vs general models are "not
   comparable" per the dataset card — julia-1's own card reports this very benchmark).
2. **…but its probabilities are unusable for automation on this data**: NLL 3.44,
   KL 2.81, coverage@5 % = **0.001** (i.e. almost nothing can be auto-accepted at a 5 %
   error budget despite 72.5 % accuracy). Point-estimate accurate, distribution wrong.
3. **kev-4b is the automation pick**: 0.630 accuracy with the best probability quality
   (Brier 0.195, KL 0.335) and cov@5 % 0.069 — 69× julia-1's automatable share.
4. **lev has the best ECE (0.087)** but is the slowest (p50 1.1 s — GPU-offloaded 4B).
5. **laya underperforms here (0.340, below the 0.470 prior)** — consistent with its
   moderation/guardrail specialization and its short trained token budget (long
   agent-trace states get truncated per the llama.cpp README); on short clear-cut cases
   it behaves normally (0.530 on fixtures at 30 ms).
6. Fixture vs typed gap (kev-4b 0.727 vs 0.630) shows the fixture suite measures
   "can the model read a clean case at all", typed-decisions measures real-world mess.

Per-model load times (excluded from latency): julia-1 1.2 s · laya 0.7 s · kev-0.8b
2.2 s · lev 4.2–4.7 s · kev-4b 4.7 s. Mean case latency on the full 400-case run:
julia-1 55 ms · laya 141 ms · kev-0.8b 582 ms · kev-4b 850 ms · lev 1 136 ms.

### 7.3 How to read this

- `acc` on typed-decisions must be compared to the **0.470 prior floor** and the
  **0.735 teacher ceiling** (§6); anything in between reflects agreement with the
  teacher ensemble, not ground truth. Specialists (julia-1) and generalists (kev, lev)
  are not directly comparable per the dataset card.
- Calibration matters more than accuracy for automation: Brier/NLL/KL and `cov@5 %`
  (share of decisions you can automate at ≤5 % empirical error using confidence
  thresholds) decide whether the model is usable in a loop — julia-1 vs kev-4b is the
  textbook illustration (§7.2, points 2-3).
- Latency here is per-case (one request carrying all questions) on a desktop
  (CPU for the encoders, GPU-offloaded 4B models); llama.cpp scales probabilities with
  per-model stored temperatures — calibration is deployment-specific, re-fit on your data.

## 8. Reproduce

```bash
uv sync
uv run decision-bench validate-config
uv run decision-bench run --suite fixture                       # real models
uv run decision-bench run --suite typed-decisions               # 400 cases x 5 models
uv run decision-bench run --suite fixture --mock                # offline pipeline check
# single model / attach to a running server:
uv run decision-bench run --suite typed-decisions --models julia-1
uv run decision-bench run --base-url http://127.0.0.1:8080 --suite fixture
```

Models live in `D:/Modeles_LLM/Decision/<Family>/` (Q8_0); server binary and model paths
are declared only in `configs/bench.toml`.

## 9. Sources

- llama.cpp PR #29818 (merged 2026-10-02) and `tools/server/README.md` @ master
  `cb7934c5` (pinned copy: `scratch/upstream_docs/llama-cpp/`)
- Model cards: `SupersonicLabs/Julia-1`, `convaiinnovations/laya`, `interfaze-ai/lev`,
  `openjev/openjev`, `jaredpalmer/kev-4b`, ggml-org GGUF repos
- Dataset card: `LocalLLaMA/typed-decisions` (pinned copy in `scratch/upstream_docs/models/`)
- Protocol: `AbdelStark/jev-benchmarks` README + `docs/PROTOCOL.md` (pinned copies)
- TypeSafe/Jev dossier: `C:/GIT/jev-ai` (incl. `typesafe-docs/api.md` — the API
  llama.cpp replicates — and the official eval figures)
- Laya technical dossier: `C:/GIT/Laya/docs/` (architecture, RLCD, ActHead, calibration)
