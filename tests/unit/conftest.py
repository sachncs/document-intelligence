"""Pytest fixtures for unit tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Apply the shared env contract for every unit test.

    Deleting stale env vars from prior runs keeps tests deterministic.
    """
    monkeypatch.setenv("STORE_PATH", str(tmp_path / "docendo.sqlite3"))
    test_env = {
        "CHAT_KEY": "test-key-not-real",
        "CHAT_URL": "https://api.example.com/v1",
        "CHAT_MODEL": "test-model",
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
    }
    for k, v in test_env.items():
        monkeypatch.setenv(k, v)
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
