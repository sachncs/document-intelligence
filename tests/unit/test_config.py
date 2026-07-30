"""Tests for Settings configuration."""

from __future__ import annotations

import pytest

from docendo.config import Settings
from docendo.exceptions import ConfigurationError


class TestSettings:
    def test_litellm_model_prefix(self, settings: Settings) -> None:
        assert settings.litellm_model == "minimax/MiniMax-M3"

    def test_litellm_embedding_model_prefix_preserves_existing(self, settings: Settings) -> None:
        # BFSI_EMBEDDING_MODEL already contains a slash (Qwen/Qwen3-Embedding-8B),
        # so litellm_embedding_model should not double-prefix.
        assert settings.litellm_embedding_model == "Qwen/Qwen3-Embedding-8B"

    def test_require_llm_raises_on_empty(self, settings: Settings) -> None:
        settings.minimax_api_key = ""
        with pytest.raises(ConfigurationError):
            settings.require_llm()

    def test_require_embeddings_raises_when_missing(self, settings: Settings) -> None:
        settings.bfsi_embedding_api_key = ""
        with pytest.raises(ConfigurationError):
            settings.require_embeddings()

    def test_require_for_run_passes_when_configured(self, settings: Settings) -> None:
        # Should not raise.
        settings.require_for_run()

    def test_tokenizer_match_passes_when_equal(self, settings: Settings) -> None:
        settings.validate_tokenizer_match()

    def test_tokenizer_mismatch_raises_by_default(self, settings: Settings) -> None:
        settings.bfsi_tokenizer_model = "Qwen/Qwen2-7B"
        with pytest.raises(ConfigurationError):
            settings.validate_tokenizer_match()

    def test_tokenizer_mismatch_allowed_when_flag_set(self, settings: Settings) -> None:
        settings.bfsi_tokenizer_model = "Qwen/Qwen2-7B"
        settings.bfsi_allow_tokenizer_mismatch = True
        settings.validate_tokenizer_match()  # should not raise

    def test_chunk_overlap_must_be_less_than_chunk_size(self, settings: Settings) -> None:
        settings.bfsi_chunk_overlap_tokens = settings.bfsi_chunk_size_tokens
        with pytest.raises(ConfigurationError):
            Settings.model_validate(settings.model_dump())

    def test_default_paths(self, settings: Settings) -> None:
        assert settings.bfsi_sqlite_path.name == "rbi-circulars.sqlite3"
        assert settings.bfsi_chunk_size_tokens == 384
        assert settings.bfsi_chunk_overlap_tokens == 64
        assert settings.bfsi_embedding_dims == 4096
