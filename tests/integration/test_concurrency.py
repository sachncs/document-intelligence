"""Concurrency tests for the SQLite store."""

from __future__ import annotations

import asyncio
import math
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from docendo.config import reset_settings_cache
from docendo.retrieval._internal import reset_retriever_cache
from docendo.retrieval.store import SQLiteStore

DIMS = 4


def _normalize(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _fake_embed(texts: list[str], *, settings=None) -> list[list[float]]:
    return [_normalize([((abs(hash(t)) >> i) & 0xFF) / 255.0 for i in range(DIMS)]) for t in texts]


def _record(circ: str, text: str, hash_: str) -> dict:
    return {
        "circular_id": circ,
        "title": f"Title {circ}",
        "text": text,
        "issue_date": "2024-01-15",
        "topic": "kyc",
        "source_url": f"https://rbi.org.in/{circ}",
        "page_start": 1,
        "page_end": 1,
        "chunk_index": 0,
        "chunk_count": 1,
        "extraction_method": "text",
        "content_hash": hash_,
        "embedding": _fake_embed([text])[0],
    }


@pytest.fixture
def tmp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "rbi.sqlite3"
    monkeypatch.setenv("BFSI_SQLITE_PATH", str(db))
    monkeypatch.setenv("BFSI_EMBEDDING_DIMS", str(DIMS))
    monkeypatch.setenv("BFSI_EMBEDDING_API_KEY", "test-key")
    monkeypatch.setenv("BFSI_EMBEDDING_API_BASE", "https://embed.example.com")
    monkeypatch.setenv("BFSI_EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-8B")
    monkeypatch.setenv("BFSI_TOKENIZER_MODEL", "Qwen/Qwen3-Embedding-8B")
    reset_settings_cache()
    reset_retriever_cache()
    yield db
    reset_retriever_cache()
    reset_settings_cache()


class TestConcurrency:
    def test_concurrent_readers_one_writer(self, tmp_db: Path) -> None:
        store = SQLiteStore(tmp_db)
        try:
            store.ensure_schema()
            # Pre-populate with some data so reads have something to do.
            for i in range(5):
                store.upsert_chunks(f"PRE{i}", [_record(f"PRE{i}", f"text {i}", f"h{i}")])

            errors: list[str] = []

            def reader() -> None:
                try:
                    for _ in range(50):
                        store.count()
                        store.list_recent("2023-01-01")
                except Exception as exc:
                    errors.append(f"reader: {exc}")

            def writer(idx: int) -> None:
                try:
                    rec = _record(f"W{idx}", f"text {idx}", f"wh{idx}")
                    store.upsert_chunks(f"W{idx}", [rec])
                except Exception as exc:
                    errors.append(f"writer{idx}: {exc}")

            threads = [threading.Thread(target=reader) for _ in range(5)]
            threads.append(threading.Thread(target=writer, args=(0,)))
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)
                assert not t.is_alive()
            assert not errors, errors
        finally:
            store.close()

    def test_async_concurrent_queries(self, tmp_db: Path) -> None:
        """10 concurrent hybrid_search calls complete without error."""

        from docendo.retrieval.types import SearchResponse

        store = SQLiteStore(tmp_db)
        try:
            store.ensure_schema()
            for i in range(5):
                store.upsert_chunks(f"C{i}", [_record(f"C{i}", f"kyc rule {i}", f"h{i}")])

            with patch(
                "docendo.retrieval.embedder.async_embed_texts",
                side_effect=lambda texts, *, settings=None: [_normalize([0.0] * DIMS) for _ in texts],
            ):

                async def one_query() -> SearchResponse:
                    # SQLite calls are sync; offload.
                    return await asyncio.to_thread(store.hybrid_search, "kyc", 5)

                async def many() -> None:
                    results = await asyncio.gather(*[one_query() for _ in range(10)])
                    assert all(isinstance(r, SearchResponse) for r in results)
                    assert all(len(r.hits) >= 0 for r in results)

                asyncio.run(many())
        finally:
            store.close()
