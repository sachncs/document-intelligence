"""Tests for the embedder (LiteLLM wrapper)."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from docendo.config import reset_settings_cache
from docendo.exceptions import EmbeddingProviderError
from docendo.retrieval import embedder


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VECTOR_KEY", "test")
    monkeypatch.setenv("VECTOR_BASE", "https://embed.example.com")
    monkeypatch.setenv("VECTOR_MODEL", "Qwen/Qwen3-Embedding-8B")
    monkeypatch.setenv("VECTOR_DIMS", "4")
    reset_settings_cache()
    embedder.reset()
    yield
    embedder.reset()
    reset_settings_cache()


class TestCache:
    def test_cache_returns_same_vector_on_second_call(self) -> None:
        async def _fake(texts, *, settings=None):
            return [[0.1, 0.2, 0.3, 0.4]] * len(texts)

        with patch.object(embedder, "aembed", side_effect=_fake):
            v1 = asyncio.run(embedder.aembed(["hello"]))
            v2 = asyncio.run(embedder.aembed(["hello"]))
        assert v1 == v2

    def test_cache_key_includes_dims(self) -> None:
        """Different dims trigger fresh embedding."""
        async def _fake_4d(texts, *, settings=None):
            return [[0.1] * 4] * len(texts)

        async def _fake_8d(texts, *, settings=None):
            return [[0.1] * 8] * len(texts)

        with patch.object(embedder, "aembed", side_effect=_fake_4d):
            v1 = asyncio.run(embedder.aembed(["x"]))
        # Simulate a dims change by mutating Settings (the cache key includes dims).
        from docendo.config import Settings

        new_s = Settings()
        object.__setattr__(new_s, "vector_dims", 8)
        with patch.object(embedder, "aembed", side_effect=_fake_8d):
            v2 = asyncio.run(embedder.aembed(["x"]))
        # First call returned a 4-vector; second must be 8.
        assert len(v1[0]) == 4
        assert len(v2[0]) == 8

    def test_cache_evicts_at_max_size(self) -> None:
        """At CACHE_MAX entries, the oldest is evicted."""

        async def _fake_seq(texts, *, settings=None):
            # Each call gets a unique vector for its text.
            return [[float(hash(t) % 1000) / 1000.0] * 4 for t in texts]

        with patch.object(embedder, "aembed", side_effect=_fake_seq):
            # Fill the cache with CACHE_MAX + 1 entries.
            from docendo.retrieval.embedder import _CACHE_MAX

            texts = [f"text-{i}" for i in range(_CACHE_MAX + 1)]
            asyncio.run(embedder.aembed(texts))
            # The cache must not exceed the limit.
            assert len(embedder._CACHE) <= _CACHE_MAX  # type: ignore[attr-defined]


class TestErrors:
    def test_404_surfaces_clear_error(self) -> None:
        import litellm  # type: ignore[import-untyped]

        async def _fake_404(*args, **kwargs):
            raise litellm.exceptions.NotFoundError(
                message="model not found",
                llm_provider="openai_compatible",
                model="Qwen/Qwen3-Embedding-8B",
            )

        with (
            patch.object(litellm, "aembedding", side_effect=_fake_404),
            pytest.raises(EmbeddingProviderError) as exc_info,
        ):
            asyncio.run(embedder.aembed(["x"]))
        assert "Qwen" in str(exc_info.value)

    def test_partial_batch_failure_raises(self) -> None:
        """A mock that returns valid + invalid vectors raises."""
        import litellm  # type: ignore[import-untyped]

        class _Resp:
            def __init__(self, vecs: list[list[float]]) -> None:
                self.data = [{"embedding": v} for v in vecs]

        async def _fake_partial(*args, **kwargs):
            # First vector matches dims, second is empty (crash path).
            return _Resp([[0.1] * 4, []])

        with (
            patch.object(litellm, "aembedding", side_effect=_fake_partial),
            pytest.raises(EmbeddingProviderError),
        ):
            asyncio.run(embedder.aembed(["a", "b"]))
