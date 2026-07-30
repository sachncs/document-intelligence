"""LiteLLM embedding wrapper with batching, retries, and a process-local cache.

Embeddings are cached in memory keyed by ``(model, dims, sha256(text))``. The
on-disk SQLite store is the persistent cache; this in-memory cache avoids
re-embedding the same text within a single process.
"""

from __future__ import annotations

import asyncio
import hashlib
import math
from collections import OrderedDict
from typing import Any

import litellm

from docendo.config import Settings, get_settings
from docendo.exceptions import EmbeddingProviderError

_CACHE_MAX = 8192
_CACHE: OrderedDict[tuple[Any, ...], list[float]] = OrderedDict()


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _cache_key(text: str, settings: Settings) -> tuple[Any, ...]:
    return (
        _hash(text),
        settings.litellm_embedding_model,
        settings.bfsi_embedding_dims,
    )


def _cache_get(key: tuple[Any, ...]) -> list[float] | None:
    if key not in _CACHE:
        return None
    _CACHE.move_to_end(key)
    return _CACHE[key]


def _cache_set(key: tuple[Any, ...], vec: list[float]) -> None:
    _CACHE[key] = vec
    _CACHE.move_to_end(key)
    while len(_CACHE) > _CACHE_MAX:
        _CACHE.popitem(last=False)


def reset_embedding_cache() -> None:
    """Clear the in-memory embedding cache (used by tests)."""
    _CACHE.clear()


async def async_embed_texts(
    texts: list[str],
    *,
    settings: Settings | None = None,
) -> list[list[float]]:
    """Embed ``texts`` via LiteLLM in batches.

    Returns one vector per input, in input order. Each vector has length
    ``settings.bfsi_embedding_dims``; a length mismatch raises
    :class:`EmbeddingProviderError`.
    """
    settings = settings or get_settings()
    if not texts:
        return []

    batch_size = max(1, settings.bfsi_embedding_batch_size)
    api_base = settings.bfsi_embedding_api_base.rstrip("/")
    if not api_base.endswith("/v1"):
        api_base = f"{api_base}/v1"

    vectors: list[list[float] | None] = [None] * len(texts)
    uncached_idx: list[int] = []

    for i, t in enumerate(texts):
        hit = _cache_get(_cache_key(t, settings))
        if hit is not None:
            vectors[i] = hit
        else:
            uncached_idx.append(i)

    if not uncached_idx:
        return [v if v is not None else [] for v in vectors]

    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            for start in range(0, len(uncached_idx), batch_size):
                batch = uncached_idx[start : start + batch_size]
                batch_texts = [texts[i] for i in batch]
                resp = await litellm.aembedding(
                    model=settings.litellm_embedding_model,
                    input=batch_texts,
                    api_key=settings.bfsi_embedding_api_key,
                    api_base=api_base,
                    timeout=settings.bfsi_llm_timeout,
                )
                for offset, item in enumerate(resp["data"]):
                    vec = list(item["embedding"])
                    if len(vec) != settings.bfsi_embedding_dims:
                        raise EmbeddingProviderError(
                            f"Embedding dim mismatch: expected "
                            f"{settings.bfsi_embedding_dims}, got {len(vec)}. "
                            "Update BFSI_EMBEDDING_DIMS or pick a different model."
                        )
                    vectors[batch[offset]] = vec
                    _cache_set(_cache_key(batch_texts[offset], settings), vec)
            break
        except EmbeddingProviderError:
            raise
        except Exception as exc:
            last_exc = exc
            if attempt == 2:
                break
            await asyncio.sleep(0.5 * (2**attempt))
    else:  # pragma: no cover - loop exhausted without break
        pass
    if last_exc is not None and any(v is None for v in vectors):
        raise EmbeddingProviderError(
            f"Embedding call failed for {settings.litellm_embedding_model!r} "
            f"at {api_base!r}: {last_exc}"
        ) from last_exc

    return [v if v is not None else [] for v in vectors]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two equal-length vectors; 0.0 on size mismatch."""
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


__all__ = ["async_embed_texts", "cosine_similarity", "reset_embedding_cache"]
