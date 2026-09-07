"""Provider-fallback tests for the embedding layer."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import litellm  # type: ignore[import-untyped]
import pytest
from docendo.config import reset_settings_cache
from docendo.exceptions import EmbeddingProviderError
from docendo.retrieval import embedder


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VECTOR_KEY", "test-key")
    monkeypatch.setenv("VECTOR_BASE", "https://embed.example.com")
    monkeypatch.setenv("VECTOR_MODEL", "Qwen/Qwen3-Embedding-8B")
    monkeypatch.setenv("TOKENIZER_MODEL", "Qwen/Qwen3-Embedding-8B")
    monkeypatch.setenv("VECTOR_DIMS", "4")
    reset_settings_cache()
    embedder.reset()
    yield
    embedder.reset()
    reset_settings_cache()


class TestProviderErrors:
    def test_404_surfaces_clear_error(self) -> None:
        """A 404 from the embedding endpoint raises EmbeddingProviderError with
        the configured model id and base URL."""

        async def _fake_aembedding(*args, **kwargs):
            raise litellm.exceptions.NotFoundError(
                message="model not found",
                llm_provider="openai_compatible",
                model="Qwen/Qwen3-Embedding-8B",
            )

        with (
            patch.object(litellm, "aembedding", side_effect=_fake_aembedding),
            pytest.raises(EmbeddingProviderError) as exc_info,
        ):
            asyncio.run(embedder.aembed(["hello"]))
        assert "Qwen" in str(exc_info.value)
        assert "embed.example.com" in str(exc_info.value)
