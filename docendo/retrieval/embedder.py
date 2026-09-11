"""LiteLLM embedding wrapper with batching, retries, and a process-local cache.

Embeddings are cached in memory keyed by ``(vector_id, dims, sha256(text))``.
The on-disk SQLite store is the persistent cache; this in-memory cache avoids
re-embedding the same text within a single process.

Empty vectors raise :class:`EmbeddingProviderError` immediately rather than
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

CACHE_MAX = 8192
CACHE: OrderedDict[tuple[Any, ...], list[float]] = OrderedDict()


def hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def key(text: str, settings: Settings) -> tuple[Any, ...]:
    return (hash(text), settings.vector_id, settings.vector_dims)


def get(k: tuple[Any, ...]) -> list[float] | None:
    if k not in CACHE:
        return None
    CACHE.move_to_end(k)
    return CACHE[k]


def put(k: tuple[Any, ...], vec: list[float]) -> None:
    CACHE[k] = vec
    CACHE.move_to_end(k)
    while len(CACHE) > CACHE_MAX:
        CACHE.popitem(last=False)


def reset() -> None:
    """Clear the in-memory embedding cache (used by tests)."""
    CACHE.clear()


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


async def aembed(
    texts: list[str],
    *,
    settings: Settings | None = None,
) -> list[list[float]]:
    """Embed ``texts`` via LiteLLM in batches.

    Returns one vector per input, in input order. Each vector has length
    ``settings.vector_dims``; a length mismatch raises
    :class:`EmbeddingProviderError`.

    Retries on transient network errors (``APIConnectionError``, ``Timeout``).
    Any other litellm exception (e.g. ``NotFoundError``, ``BadRequestError``)
    is wrapped as :class:`EmbeddingProviderError` and raised immediately
    so the user gets a single typed error path.
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

    last_exc: BaseException | None = None
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
            break
        except EmbeddingProviderError:
            raise
        except (
            litellm.APIConnectionError,  # type: ignore[attr-defined]
            litellm.exceptions.Timeout,
        ) as exc:
            last_exc = exc
            if attempt == 2:
                break
            await asyncio.sleep(0.5 * (2**attempt))
        except (
            litellm.APIError,  # type: ignore[attr-defined]
            litellm.NotFoundError,  # type: ignore[attr-defined]
            litellm.AuthenticationError,  # type: ignore[attr-defined]
            litellm.BadRequestError,  # type: ignore[attr-defined]
            litellm.PermissionDeniedError,  # type: ignore[attr-defined]
            litellm.RateLimitError,  # type: ignore[attr-defined]
        ) as exc:
            raise EmbeddingProviderError(
                f"Embedding call failed for {settings.vector_id!r} at {api_base!r}: "
                f"{type(exc).__name__}: {exc}"
            ) from exc

    if all(v is not None for v in vectors):
        for i in uncached_idx:
            assert vectors[i] is not None
            put(key(texts[i], settings), vectors[i])  # type: ignore[arg-type]

    if any(v is None for v in vectors):
        if last_exc is not None:
            raise EmbeddingProviderError(
                f"Embedding call failed for {settings.vector_id!r} at {api_base!r} "
                f"after 3 attempts"
            ) from last_exc
        missing = [i for i, v in enumerate(vectors) if v is None]
        raise EmbeddingProviderError(
            f"Embedding returned no vector for inputs at indices {missing}"
        )

    return vectors  # type: ignore[return-value]


__all__ = ["aembed", "cosine", "reset"]
