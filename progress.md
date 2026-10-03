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
- [ ] Q8_0 GGUFs downloaded to D:/Modeles_LLM/Decision/ (background task).
- [ ] Bench implemented and validated (contract C1-C16).

## Contract Validation
- (to be filled at validation time: criterion, command, exit code, key numbers)
