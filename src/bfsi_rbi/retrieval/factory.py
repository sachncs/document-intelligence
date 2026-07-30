"""Process-wide retriever cache keyed by SQLite path."""

from __future__ import annotations

from functools import lru_cache

from bfsi_rbi.config import Settings, get_settings
from bfsi_rbi.retrieval.sqlite_store import SQLiteStore
from bfsi_rbi.retrieval.types import Retriever


@lru_cache(maxsize=4)
def _cached_store(path: str, settings_id: int) -> SQLiteStore:
    """One SQLiteStore per (path, settings) pair per process."""
    # We pass a Settings instance via the closure-friendly trick of using
    # get_settings() inside SQLiteStore (which accepts settings= override).
    # settings_id is included in the cache key so a settings change forces a
    # fresh store.
    settings = get_settings()
    return SQLiteStore(path, settings=settings)


def get_retriever(settings: Settings | None = None) -> Retriever:
    """Return the cached :class:`SQLiteStore` for the configured path."""
    settings = settings or get_settings()
    return _cached_store(str(settings.bfsi_sqlite_path), id(settings))


def reset_retriever_cache() -> None:
    """Drop the cached store (used by tests)."""
    _cached_store.cache_clear()


__all__ = ["get_retriever", "reset_retriever_cache"]
