"""End-to-end pipeline over the in-process mock backend (contracts C9, C12-partial) — offline."""

from __future__ import annotations

import json
from pathlib import Path

from decision_bench.cli import main
from decision_bench.config import BenchConfig, ModelConfig, ServerConfig, load_config
from decision_bench.datasets import load_suite
from decision_bench.report import write_summary_md
from decision_bench.runner import run_model


def _cfg(tmp_path: Path) -> BenchConfig:
    return BenchConfig(
        server=ServerConfig(binary=""),
        models=[ModelConfig(name="mock-model", gguf_path="none")],
        output_dir=tmp_path,
        request_timeout_s=10.0,
    )


def test_e2e_fixture_on_mock(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    cases = load_suite("fixture", limit=6)
    run = run_model(cfg, cfg.models[0], "fixture", cases, tmp_path, mock=True)
    assert run.error is None
    assert run.summary["n_questions"] == 24  # 6 cases x 4 questions
    assert run.summary["failures"] == 0
    assert set(run.summary["by_type"]) == {"choice", "score", "noul"}

    payload = json.loads((tmp_path / "mock-model__fixture.json").read_text(encoding="utf-8"))
    assert payload["summary"]["n_questions"] == 24
    assert payload["records"][0]["case_id"] == cases[0].case_id

    md_path = write_summary_md([run], "fixture", len(cases), cfg.error_budget, tmp_path)
    text = md_path.read_text(encoding="utf-8")
    assert "mock-model" in text and "Q8_0" in text


def test_e2e_cli_validate_config(tmp_path: Path) -> None:
    toml = tmp_path / "bench.toml"
    toml.write_text(
        "\n".join(
            [
                "[server]",
                'binary = "C:/llama.cpp/llama-server.exe"',
                "port = 8080",
                "[bench]",
                'output_dir = "results"',
                "[[models]]",
                'name = "julia-1"',
                'gguf_path = "D:/Modeles_LLM/Decision/Julia-1/Julia-1-Q8_0.gguf"',
                "enabled = true",
                "[[models]]",
                'name = "openjev"',
                'gguf_path = "D:/Modeles_LLM/Decision/OpenJev/OpenJev-Q8_0.gguf"',
                "enabled = false",
            ]
        ),
        encoding="utf-8",
    )
    cfg = load_config(toml)
    assert cfg.server.port == 8080
    assert [m.name for m in cfg.models] == ["julia-1", "openjev"]
    assert cfg.models[1].enabled is False
    assert main(["validate-config", "--config", str(toml)]) == 0


def test_cli_rejects_unknown_model(tmp_path: Path) -> None:
    toml = tmp_path / "bench.toml"
    toml.write_text(
        "[[models]]\nname = \"a\"\ngguf_path = \"x\"\n",
        encoding="utf-8",
    )
    assert main(["run", "--config", str(toml), "--suite", "fixture", "--models", "nope", "--mock"]) == 2


def test_cli_mock_run_writes_reports(tmp_path: Path) -> None:
    toml = tmp_path / "bench.toml"
    toml.write_text("[[models]]\nname = \"fixture-model\"\ngguf_path = \"x\"\nenabled = true\n", encoding="utf-8")
    out = tmp_path / "results"
    code = main(
        [
            "run",
            "--config",
            str(toml),
            "--suite",
            "fixture",
            "--limit",
            "3",
            "--mock",
            "--output",
            str(out),
        ]
    )
    assert code == 0
    run_dirs = list(out.iterdir())
    assert len(run_dirs) == 1
    files = {p.name for p in run_dirs[0].iterdir()}
    assert "summary.md" in files
    assert any(name.startswith("fixture-model__") for name in files)
