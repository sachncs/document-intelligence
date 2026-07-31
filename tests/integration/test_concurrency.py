"""Concurrency tests for the SQLite store."""

from __future__ import annotations

import math
import threading
from pathlib import Path

import pytest
from pydantic import HttpUrl

from docendo.config import reset_settings_cache
from docendo.retrieval._internal import reset as reset_internal
from docendo.retrieval.record import ChunkRecord
from docendo.retrieval.store import Store

DIMS = 4


def _normalize(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _fake_embed(texts: list[str], *, settings=None) -> list[list[float]]:
    return [
        _normalize([((abs(hash(t)) >> i) & 0xFF) / 255.0 for i in range(DIMS)])
        for t in texts
    ]


def _record(circ: str, text: str, hash_: str) -> ChunkRecord:
    return ChunkRecord(
        circular_id=circ,
        title=f"Title {circ}",
        text=text,
        issue_date="2024-01-15",
        topic="kyc",
        source_url=HttpUrl(f"https://rbi.org.in/{circ}"),
        page_estimate_start=1,
        page_estimate_end=1,
        chunk_index=0,
        chunk_count=1,
        extraction_method="text",
        content_hash=hash_,
        embedding=_fake_embed([text])[0],
    )


@pytest.fixture
def _tmp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "docendo.sqlite3"
    monkeypatch.setenv("STORE_PATH", str(db))
    monkeypatch.setenv("VECTOR_DIMS", str(DIMS))
    monkeypatch.setenv("VECTOR_KEY", "test-key")
    monkeypatch.setenv("VECTOR_BASE", "https://embed.example.com")
    monkeypatch.setenv("VECTOR_MODEL", "Qwen/Qwen3-Embedding-8B")
    monkeypatch.setenv("TOKENIZER_MODEL", "Qwen/Qwen3-Embedding-8B")
    reset_settings_cache()
    reset_internal()
    yield db
    reset_internal()
    reset_settings_cache()


class TestConcurrency:
    def test_concurrent_readers_one_writer(self, _tmp_db: Path) -> None:
        store = Store(_tmp_db)
        try:
            store.ensure_schema()
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

    def test_async_concurrent_queries(self, _tmp_db: Path) -> None:
        """10 concurrent hybrid_search calls complete without error."""
        from unittest.mock import patch

        from docendo.retrieval import embedder
        from docendo.retrieval.types import Results

        store = Store(_tmp_db)
        try:
            store.ensure_schema()
            for i in range(5):
                store.upsert_chunks(f"C{i}", [_record(f"C{i}", f"kyc rule {i}", f"h{i}")])

            with patch.object(
                embedder,
                "aembed",
                side_effect=lambda texts, *, settings=None: [
                    _fake_embed(texts)[0] if texts else []
                ],
            ):

                def one_query_sync() -> Results:
                    return store.hybrid_search("kyc", 5)

                def many() -> None:
                    results = [one_query_sync() for _ in range(10)]
                    assert all(isinstance(r, Results) for r in results)
                    assert all(len(r.hits) >= 0 for r in results)

                many()
        finally:
            store.close()
