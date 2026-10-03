# Decision models comparison

- Suite: `typed-decisions` (400 cases)
- Quantization: Q8_0 for every model (matched-weights comparison rule).
- Generated: 2026-10-03 09:29 UTC
- Server: version: 0.5.0-dev (build 11370, commit bed0a8566)
- Python: 3.12.9
- decision-bench: 0.1.0
- Backend: llama-server spawned per model (127.0.0.1:8080)
- Grading: choice=argmax vs gold; score=round(expected) vs gold level (+MAE in JSON); noul=p(true)>=0.5.
- Probabilities are NOT guaranteed calibrated (llama.cpp scales them with per-model temperatures);
  read Brier/NLL/ECE/KL alongside accuracy, per the typed-decisions dataset card.

| model | acc | acc choice | acc score | acc noul | acc | F1 | Brier | NLL | ECE10 | KL | cov@5% | p50 s | p95 s | tok/case | GB | fails |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| julia-1 | 0.725 | 0.710 | 0.679 | 0.800 | 0.725 | 0.575 | 0.381 | 3.441 | 0.227 | 2.810 | 0.001 | 0.053 | 0.076 | 1458.9 | 0.168 | 0 |
| laya | 0.340 | 0.287 | 0.273 | 0.483 | 0.340 | 0.179 | 0.399 | 1.324 | 0.112 | 0.693 | 0.000 | 0.152 | 0.210 | 1449.7 | 0.449 | 0 |
| lev | 0.588 | 0.617 | 0.439 | 0.758 | 0.588 | 0.467 | 0.218 | 1.013 | 0.087 | 0.382 | 0.042 | 1.100 | 1.475 | 2463.6 | 4.482 | 0 |
| kev-0.8b | 0.429 | 0.508 | 0.295 | 0.530 | 0.429 | 0.338 | 0.277 | 1.106 | 0.152 | 0.475 | 0.019 | 0.603 | 0.800 | 1405.0 | 0.812 | 0 |
| kev-4b | 0.630 | 0.642 | 0.530 | 0.753 | 0.630 | 0.440 | 0.195 | 0.966 | 0.153 | 0.335 | 0.069 | 0.863 | 1.074 | 1405.0 | 4.484 | 0 |

Notes:
- Failed requests are counted in `fails` and stay in the denominator (no silent retry).
- `cov@5%` = share of questions automatable at empirical error <= 5% (highest confidence first).
- Latency is per-case (one HTTP request with all questions of the case); model load, settle delay and warmup are excluded (load time is reported as `server_load_s` in the JSON).
