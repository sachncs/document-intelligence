"""Provider-fallback tests for the embedding layer."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from bfsi_rbi.config import reset_settings_cache
from bfsi_rbi.retrieval import embeddings


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BFSI_EMBEDDING_API_KEY", "test-key")
    monkeypatch.setenv("BFSI_EMBEDDING_API_BASE", "https://embed.example.com")
    monkeypatch.setenv("BFSI_EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-8B")
    monkeypatch.setenv("BFSI_TOKENIZER_MODEL", "Qwen/Qwen3-Embedding-8B")
    monkeypatch.setenv("BFSI_EMBEDDING_DIMS", "4")
    reset_settings_cache()
    yield
    reset_settings_cache()


@pytest.mark.integration
class TestProviderErrors:
    def test_404_surfaces_clear_error(self) -> None:
        """A 404 from the embedding endpoint raises EmbeddingProviderError with
        the configured model id and base URL."""
        import litellm

        async def _fake_aembedding(*args, **kwargs):
            raise litellm.exceptions.NotFoundError(
                message="model not found", llm_provider="openai_compatible", model="Qwen/Qwen3-Embedding-8B"
            )

        with patch.object(litellm, "aembedding", side_effect=_fake_aembedding):
            with pytest.raises(embeddings.EmbeddingProviderError) as exc_info:
                asyncio.run(embeddings.async_embed_texts(["hello"]))
            assert "Qwen" in str(exc_info.value)
            assert "embed.example.com" in str(exc_info.value)
