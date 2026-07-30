"""Tests for Settings configuration."""

from __future__ import annotations

import pytest

from docendo.config import Settings
from docendo.exceptions import ConfigurationError


class TestSettings:
    def test_chat_property_format(self, monkeypatch) -> None:
        monkeypatch.setenv("CHAT_MODEL", "MiniMax-M3")
        s = Settings()
        assert s.chat == "minimax/MiniMax-M3"

    def test_vector_id_preserves_existing_prefix(self, monkeypatch) -> None:
        # BFSI_* env vars were removed in 0.4.0; this test guards against regressions
        # where someone re-introduces a prefixed model id with a slash.
        monkeypatch.setenv("VECTOR_MODEL", "Qwen/Qwen3-Embedding-8B")
        s = Settings()
        assert s.vector_id == "Qwen/Qwen3-Embedding-8B"

    def test_require_llm_raises_on_empty(self, monkeypatch) -> None:
        monkeypatch.setenv("CHAT_KEY", "")
        s = Settings()
        with pytest.raises(ConfigurationError):
            s.require_llm()

    def test_require_embeddings_raises_when_missing(self, monkeypatch) -> None:
        monkeypatch.setenv("VECTOR_KEY", "")
        monkeypatch.setenv("VECTOR_BASE", "")
        s = Settings()
        with pytest.raises(ConfigurationError):
            s.require_embeddings()

    def test_require_for_run_passes_when_configured(self, monkeypatch) -> None:
        monkeypatch.setenv("CHAT_KEY", "test")
        monkeypatch.setenv("VECTOR_KEY", "test")
        monkeypatch.setenv("VECTOR_BASE", "https://embed.example.com")
        s = Settings()
        # Should not raise.
        s.require_for_run()

    def test_tokenizer_match_passes_when_equal(self, monkeypatch) -> None:
        monkeypatch.setenv("TOKENIZER_MODEL", "Qwen/Qwen3-Embedding-8B")
        monkeypatch.setenv("VECTOR_MODEL", "Qwen/Qwen3-Embedding-8B")
        s = Settings()
        s.validate_tokenizer_match()

    def test_tokenizer_mismatch_raises_by_default(self, monkeypatch) -> None:
        monkeypatch.setenv("TOKENIZER_MODEL", "Qwen/Qwen2-7B")
        monkeypatch.setenv("VECTOR_MODEL", "Qwen/Qwen3-Embedding-8B")
        s = Settings()
        with pytest.raises(ConfigurationError):
            s.validate_tokenizer_match()

    def test_tokenizer_mismatch_allowed_when_flag_set(self, monkeypatch) -> None:
        monkeypatch.setenv("TOKENIZER_MODEL", "Qwen/Qwen2-7B")
        monkeypatch.setenv("VECTOR_MODEL", "Qwen/Qwen3-Embedding-8B")
        monkeypatch.setenv("TOKENIZER_ALLOW_MISMATCH", "1")
        s = Settings()
        s.validate_tokenizer_match()  # should not raise

    def test_chunk_overlap_must_be_less_than_chunk_size(self, monkeypatch) -> None:
        monkeypatch.setenv("CHUNK_OVERLAP", "500")
        monkeypatch.setenv("CHUNK_SIZE", "500")
        with pytest.raises(ConfigurationError):
            Settings()

    def test_default_paths(self, monkeypatch) -> None:
        # Defaults from the new env-driven Settings.
        monkeypatch.delenv("STORE_PATH", raising=False)
        monkeypatch.delenv("VECTOR_DIMS", raising=False)
        s = Settings()
        assert s.store_path.name == "docendo.sqlite3"
        assert s.chunk_size == 384
        assert s.chunk_overlap == 64
        assert s.vector_dims == 4096
