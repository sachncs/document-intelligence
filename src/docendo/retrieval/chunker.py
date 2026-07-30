"""Gigatoken wrapper for chunking.

Caches the per-process tokenizer instance so the model load happens at most
once. Chunking decodes slices back to text so the downstream FTS5 unicode61
tokenizer and the embedding model see plain text (not token ids).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from docendo.config import Settings, get_settings
from docendo.exceptions import ConfigurationError


@lru_cache(maxsize=1)
def tokenizer() -> Any:
    """Lazy-load and cache the gigatoken tokenizer."""
    import gigatoken as gt

    settings = get_settings()
    return gt.Tokenizer(settings.tokenizer_model)


def reset() -> None:
    """Clear the tokenizer cache (used by tests)."""
    tokenizer.cache_clear()


def encode(text: str, settings: Settings | None = None) -> list[int]:
    """Encode text to token ids using the configured tokenizer."""
    settings = settings or get_settings()
    try:
        result = tokenizer().encode(text)
    except Exception as exc:
        raise ConfigurationError(
            f"Failed to load tokenizer {settings.tokenizer_model!r}: {exc}. "
            "Check the model name and that gigatoken is installed."
        ) from exc
    try:
        return [int(x) for x in result]
    except TypeError:
        return list(result)


def chunk(
    text: str,
    *,
    chunk_size: int,
    overlap: int,
    settings: Settings | None = None,
) -> list[str]:
    """Split ``text`` into chunks of ``chunk_size`` tokens with ``overlap`` overlap.

    Returns a list of decoded strings. Empty input returns an empty list.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be in [0, chunk_size)")

    ids = encode(text, settings=settings)
    if len(ids) == 0:
        return []

    tok = tokenizer()
    chunks: list[str] = []
    step = chunk_size - overlap
    for start in range(0, len(ids), step):
        end = min(start + chunk_size, len(ids))
        slice_ids = ids[start:end]
        if len(slice_ids) == 0:
            break
        decoded = tok.decode(slice_ids)
        if isinstance(decoded, bytes):
            decoded = decoded.decode("utf-8", errors="replace")
        if decoded.strip():
            chunks.append(decoded)
        if end >= len(ids):
            break
    return chunks


__all__ = ["chunk", "encode", "reset"]
