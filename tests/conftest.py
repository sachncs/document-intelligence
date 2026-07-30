"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from bfsi_rbi.config import Settings, get_settings, reset_settings_cache


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure tests don't leak env vars to one another."""
    test_env = {
        "MINIMAX_API_KEY": "test-key-not-real",
        "MINIMAX_BASE_URL": "https://api.minimax.io/v1",
        "MINIMAX_MODEL": "MiniMax-M3",
        "BFSI_LOG_LEVEL": "WARNING",
        "BFSI_HTTP_TIMEOUT": "5",
        "BFSI_EMBEDDING_API_KEY": "test-embedding-key",
        "BFSI_EMBEDDING_API_BASE": "https://embed.example.com/v1",
        "BFSI_EMBEDDING_MODEL": "Qwen/Qwen3-Embedding-8B",
        "BFSI_TOKENIZER_MODEL": "Qwen/Qwen3-Embedding-8B",
        "BFSI_EMBEDDING_DIMS": "4096",
    }
    for k, v in test_env.items():
        monkeypatch.setenv(k, v)
    # Make sure stale ELASTIC_* env vars from a previous run never leak in.
    for stale in ("ELASTIC_URL", "ELASTIC_API_KEY", "ELASTIC_MCP_URL"):
        monkeypatch.delenv(stale, raising=False)
    reset_settings_cache()


@pytest.fixture
def settings() -> Settings:
    """Fresh Settings instance (cache is bypassed)."""
    reset_settings_cache()
    return get_settings()


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    """Empty raw/ dir under tmp_path."""
    raw = tmp_path / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    return raw
