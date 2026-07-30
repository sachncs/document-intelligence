"""LiteLLM embedding wrapper with batching, retries, and a process-local cache.

Embeddings are cached in memory keyed by ``(vector_id, dims, sha256(text))``.
The on-disk SQLite store is the persistent cache; this in-memory cache avoids
re-embedding the same text within a single process.

Empty vectors raise ``EmbeddingProviderError`` immediately rather than
returning ``[]`` (which would later crash sqlite-vector).
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


def hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def key(text: str, settings: Settings) -> tuple[Any, ...]:
    return (hash(text), settings.vector_id, settings.vector_dims)


def get(key: tuple[Any, ...]) -> list[float] | None:
    if key not in _CACHE:
        return None
    _CACHE.move_to_end(key)
    return _CACHE[key]


def put(key: tuple[Any, ...], vec: list[float]) -> None:
    _CACHE[key] = vec
    _CACHE.move_to_end(key)
    while len(_CACHE) > _CACHE_MAX:
        _CACHE.popitem(last=False)


def reset() -> None:
    """Clear the in-memory embedding cache (used by tests)."""
    _CACHE.clear()


async def aembed(
    texts: list[str],
    *,
    settings: Settings | None = None,
) -> list[list[float]]:
    """Embed ``texts`` via LiteLLM in batches.

    Returns one vector per input, in input order. Each vector has length
    ``settings.vector_dims``; a length mismatch raises
    :class:`EmbeddingProviderError`.
    """
    settings = settings or get_settings()
    if not texts:
        return []

    batch_size = max(1, settings.vector_batch)
    api_base = settings.vector_base.rstrip("/")
    if not api_base.endswith("/v1"):
        api_base = f"{api_base}/v1"

    vectors: list[list[float] | None] = [None] * len(texts)
    uncached_idx: list[int] = []

    for i, t in enumerate(texts):
        hit = get(key(t, settings))
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
                    model=settings.vector_id,
                    input=batch_texts,
                    api_key=settings.vector_key,
                    api_base=api_base,
                    timeout=settings.chat_timeout,
                )
                for offset, item in enumerate(resp["data"]):
                    vec = list(item["embedding"])
                    if len(vec) != settings.vector_dims:
                        raise EmbeddingProviderError(
                            f"Embedding dim mismatch: expected "
                            f"{settings.vector_dims}, got {len(vec)}. "
                            "Update VECTOR_DIMS or pick a different model."
                        )
                    vectors[batch[offset]] = vec
                    put(key(batch_texts[offset], settings), vec)
            break
        except EmbeddingProviderError:
            raise
        except Exception as exc:
            last_exc = exc
            if attempt == 2:
                break
            await asyncio.sleep(0.5 * (2**attempt))
    if last_exc is not None and any(v is None for v in vectors):
        raise EmbeddingProviderError(
            f"Embedding call failed for {settings.vector_id!r} at {api_base!r}: {last_exc}"
        ) from last_exc

    # Final safety net: any remaining None means the batch loop exited
    # without raising and without filling — refuse to return partial results.
    if any(v is None for v in vectors):
        missing = [i for i, v in enumerate(vectors) if v is None]
        raise EmbeddingProviderError(
            f"Embedding returned no vector for inputs at indices {missing}"
        )

    return vectors  # type: ignore[return-value]


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two equal-length vectors; 0.0 on size mismatch."""
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


__all__ = ["aembed", "cosine", "reset"]
