"""Lifecycle management for one llama-server process hosting one decision model."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import httpx

from decision_bench.config import ModelConfig, ServerConfig


class ServerStartupError(RuntimeError):
    pass


class LlamaServerManager:
    def __init__(self, server_cfg: ServerConfig, model: ModelConfig, log_dir: Path) -> None:
        if not server_cfg.binary:
            raise ServerStartupError(
                "no server binary configured: set [server].binary in configs/bench.toml, "
                "or run with --base-url / --mock"
            )
        self._cfg = server_cfg
        self._model = model
        self._log_path = log_dir / f"server__{model.name}.log"
        self._log_fh = None
        self._proc: subprocess.Popen | None = None

    @property
    def base_url(self) -> str:
        return f"http://{self._cfg.host}:{self._cfg.port}"

    def start(self) -> None:
        cmd = [
            self._cfg.binary,
            "-m",
            self._model.gguf_path,
            "--host",
            self._cfg.host,
            "--port",
            str(self._cfg.port),
            *self._model.extra_args,
        ]
        self._log_fh = open(self._log_path, "w", encoding="utf-8")  # noqa: SIM115 (lifetime = process)
        self._proc = subprocess.Popen(cmd, stdout=self._log_fh, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + self._cfg.startup_timeout_s
        with httpx.Client(timeout=2.0) as probe:
            while time.monotonic() < deadline:
                if self._proc.poll() is not None:
                    self.stop()
                    raise ServerStartupError(f"server for {self._model.name} exited early:\n{self._log_tail()}")
                try:
                    if probe.get(f"{self.base_url}/health").status_code == 200:
                        return
                except httpx.HTTPError:
                    pass
                time.sleep(0.5)
        self.stop()
        msg = (
            f"server for {self._model.name} not healthy "
            f"after {self._cfg.startup_timeout_s}s:\n{self._log_tail()}"
        )
        raise ServerStartupError(msg)

    def _log_tail(self, lines: int = 30) -> str:
        try:
            return "\n".join(self._log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])
        except OSError:
            return "<no server log>"

    def stop(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait(timeout=10)
        self._proc = None
        if self._log_fh is not None:
            self._log_fh.close()
            self._log_fh = None

    def __enter__(self) -> LlamaServerManager:
        self.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.stop()
