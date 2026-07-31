"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from docendo.config import Settings, get_settings, reset_settings_cache


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers so unknown-marker warnings disappear."""
    config.addinivalue_line(
        "markers", "perf: opt-in performance budget benchmarks (set RUN_PERF=1)"
    )
    config.addinivalue_line(
        "markers", "integration: requires live embedding / MiniMax / Network"
    )


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure tests don't leak env vars to one another."""
    test_env = {
        "CHAT_KEY": "test-key-not-real",
        "CHAT_URL": "https://api.minimax.io/v1",
        "CHAT_MODEL": "MiniMax-M3",
        "VECTOR_KEY": "test-embedding-key",
        "VECTOR_BASE": "https://embed.example.com/v1",
        "VECTOR_MODEL": "Qwen/Qwen3-Embedding-8B",
        "TOKENIZER_MODEL": "Qwen/Qwen3-Embedding-8B",
        "VECTOR_DIMS": "4",
        "VECTOR_BATCH": "8",
        "CHUNK_SIZE": "384",
        "CHUNK_OVERLAP": "64",
        "FETCH_MAX_DOCS": "5",
        "LOG_LEVEL": "WARNING",
        "HTTP_TIMEOUT": "5",
        "RRF_K": "60",
        "EVAL_CONCURRENCY": "1",
        "STORE_PATH": "/tmp/docendo-test.sqlite3",
    }
    for k, v in test_env.items():
        monkeypatch.setenv(k, v)
    # Drop stale env vars from any prior run.
    for stale in (
        "ELASTIC_URL",
        "ELASTIC_API_KEY",
        "ELASTIC_MCP_URL",
        "BFSI_LOG_LEVEL",
        "BFSI_HTTP_TIMEOUT",
        "BFSI_EMBEDDING_API_KEY",
        "BFSI_EMBEDDING_API_BASE",
        "BFSI_EMBEDDING_DIMS",
        "BFSI_EMBEDDING_MODEL",
        "BFSI_TOKENIZER_MODEL",
        "BFSI_CHUNK_SIZE_TOKENS",
        "BFSI_CHUNK_OVERLAP_TOKENS",
        "BFSI_EVAL_CONCURRENCY",
        "BFSI_INDEX_NAME",
        "BFSI_LLM_TIMEOUT",
        "MINIMAX_BASE_URL",
        "MINIMAX_API_KEY",
        "MINIMAX_MODEL",
        "RBI_FETCH_MAX_DOCS",
    ):
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
