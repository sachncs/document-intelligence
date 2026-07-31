"""Process-wide retrieval-store cache keyed by SQLite path.

Underscored module name = private boundary. Functions exported here are
single-word, no underscore prefix.
"""

from __future__ import annotations

from functools import lru_cache

from docendo.config import Settings, get_settings
from docendo.retrieval.store import Store
from docendo.retrieval.types import Retriever


@lru_cache(maxsize=4)
def cached_store(path: str, settings_id: int) -> Store:
    """One Store per (path, settings) pair per process."""
    settings = get_settings()
    return Store(path, settings=settings)


def get(settings: Settings | None = None) -> Retriever:
    """Return the cached :class:`Store` for the configured path."""
    settings = settings or get_settings()
    return cached_store(str(settings.store_path), id(settings))


def reset() -> None:
    """Drop the cached store (used by tests)."""
    cached_store.cache_clear()


__all__ = ["get", "reset"]
