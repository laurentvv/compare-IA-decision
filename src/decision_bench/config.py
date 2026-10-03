"""TOML configuration: server binary, models (gguf paths), bench parameters.

Machine paths live ONLY here (AGENTS.md §1) — the code never hardcodes them.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ModelConfig:
    name: str
    gguf_path: str
    enabled: bool = True
    extra_args: list[str] = field(default_factory=list)


@dataclass
class ServerConfig:
    binary: str = ""
    host: str = "127.0.0.1"
    port: int = 8080
    startup_timeout_s: float = 120.0
    settle_s: float = 2.0  # post-load settle before measuring (excluded from latency)


@dataclass
class BenchConfig:
    server: ServerConfig
    models: list[ModelConfig]
    output_dir: Path = Path("results")
    request_timeout_s: float = 60.0
    error_budget: float = 0.05


def load_config(path: Path) -> BenchConfig:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    srv = raw.get("server", {})
    bench = raw.get("bench", {})
    models = [
        ModelConfig(
            name=m["name"],
            gguf_path=m["gguf_path"],
            enabled=bool(m.get("enabled", True)),
            extra_args=[str(a) for a in m.get("extra_args", [])],
        )
        for m in raw.get("models", [])
    ]
    if not models:
        raise ValueError(f"no [[models]] entries in {path}")
    return BenchConfig(
        server=ServerConfig(
            binary=str(srv.get("binary", "")),
            host=str(srv.get("host", "127.0.0.1")),
            port=int(srv.get("port", 8080)),
            startup_timeout_s=float(srv.get("startup_timeout_s", 120.0)),
            settle_s=float(srv.get("settle_s", 2.0)),
        ),
        models=models,
        output_dir=Path(bench.get("output_dir", "results")),
        request_timeout_s=float(bench.get("request_timeout_s", 60.0)),
        error_budget=float(bench.get("error_budget", 0.05)),
    )


def select_models(cfg: BenchConfig, only: list[str] | None) -> list[ModelConfig]:
    chosen = [m for m in cfg.models if m.enabled] if not only else [m for m in cfg.models if m.name in only]
    if only:
        known = {m.name for m in cfg.models}
        unknown = set(only) - known
        if unknown:
            raise ValueError(f"unknown models: {sorted(unknown)}; config has {sorted(known)}")
    if not chosen:
        raise ValueError("no enabled models selected")
    return chosen
