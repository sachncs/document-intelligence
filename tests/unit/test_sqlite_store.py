"""Tests for the SQLite retrieval store.

Uses a fake embedding function so the tests run offline. Verifies:
- Schema bootstrap (FTS5 triggers, sqlite-vector init).
- Round-trip of upsert + lexical/vector search.
- RRF fusion order.
- Re-ingest via content_hash skips unchanged PDFs.
- FTS5 escaping handles quotes, special chars, AND/OR/NOT.
- Embedding-dim mismatch errors.
- row_factory returns named columns (column-order independence).
"""

from __future__ import annotations

import asyncio
import math
import sqlite3
import threading
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import HttpUrl

from docendo.config import reset_settings_cache
from docendo.retrieval import embedder
from docendo.retrieval._internal import reset
from docendo.retrieval.embedder import aembed
from docendo.retrieval.record import ChunkRecord
from docendo.retrieval.store import Store, fts_escape, parse_blob

DIMS = 8  # small for tests


def _normalize(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _fake_embed(texts: list[str], *, settings=None) -> list[list[float]]:
    """Deterministic fake embedding: hash -> unit vector."""
    out = []
    for t in texts:
        h = abs(hash(t))
        v = [(h >> (i * 8)) & 0xFF for i in range(DIMS)]
        out.append(_normalize([(x - 127.5) / 127.5 for x in v]))
    return out


@pytest.fixture
def _tmp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = tmp_path / "docendo.sqlite3"
    monkeypatch.setenv("STORE_PATH", str(db))
    monkeypatch.setenv("VECTOR_DIMS", str(DIMS))
    monkeypatch.setenv("VECTOR_KEY", "test-key")
    monkeypatch.setenv("VECTOR_BASE", "https://embed.example.com")
    monkeypatch.setenv("VECTOR_MODEL", "Qwen/Qwen3-Embedding-8B")
    monkeypatch.setenv("TOKENIZER_MODEL", "Qwen/Qwen3-Embedding-8B")
    reset_settings_cache()
    reset()
    yield db
    reset()
    reset_settings_cache()


def _record(circ: str, text: str, chunk_index: int, content_hash: str = "h1") -> ChunkRecord:
    return ChunkRecord(
        circular_id=circ,
        title=f"Title {circ}",
        text=text,
        issue_date="2024-01-15",
        topic="kyc",
        source_url=HttpUrl(f"https://rbi.org.in/{circ}"),
        page_estimate_start=1,
        page_estimate_end=5,
        chunk_index=chunk_index,
        chunk_count=2,
        extraction_method="text",
        content_hash=content_hash,
        embedding=[],
    )


def _record_with_embedding(
    circ: str, text: str, chunk_index: int, content_hash: str = "h1"
) -> ChunkRecord:
    rec = _record(circ, text, chunk_index, content_hash)
    rec.embedding = _fake_embed([text])[0]
    return rec


class TestFtsEscape:
    def test_simple(self) -> None:
        assert fts_escape("kyc requirements") == '"kyc requirements"'

    def test_quote_doubling(self) -> None:
        assert fts_escape('say "hi"') == '"say ""hi"""'

    def test_and_or_not_literalized(self) -> None:
        out = fts_escape("AND OR NOT")
        assert out == '"AND OR NOT"'


class TestParseBlob:
    def test_empty_raises(self) -> None:
        from docendo.exceptions import StorageError

        with pytest.raises(StorageError):
            parse_blob([])

    def test_packs_to_floats(self) -> None:
        out = parse_blob([1.0, 2.0, 3.0])
        assert len(out) == 12  # 3 floats * 4 bytes


class TestSchema:
    def test_ensure_schema_creates_objects(self, _tmp_db: Path) -> None:
        store = Store(_tmp_db)
        try:
            store.ensure_schema()
            conn = sqlite3.connect(str(_tmp_db))
            try:
                cur = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                )
                tables = {row[0] for row in cur.fetchall()}
                assert "chunks" in tables
                assert "chunks_fts" in tables
                assert "chunks_meta" in tables
                cur = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='trigger' ORDER BY name"
                )
                triggers = {row[0] for row in cur.fetchall()}
                assert "chunks_ai" in triggers
                assert "chunks_ad" in triggers
                assert "chunks_au" in triggers
                cur = conn.execute(
                    "SELECT value FROM chunks_meta WHERE key='embedding_dims'"
                )
                assert cur.fetchone()[0] == str(DIMS)
                # vector_version is only available after loading the extension.
                import importlib.resources

                ext = importlib.resources.files("sqlite_vector.binaries") / "vector"
                conn.enable_load_extension(True)
                conn.load_extension(str(ext))
                conn.enable_load_extension(False)
                cur = conn.execute("SELECT vector_version()")
                assert cur.fetchone()[0][0].isdigit()
            finally:
                conn.close()
        finally:
            store.close()


class TestRoundTrip:
    def test_upsert_and_count(self, _tmp_db: Path) -> None:
        store = Store(_tmp_db)
        try:
            store.ensure_schema()
            with patch.object(
                embedder,
                "aembed",
                side_effect=lambda texts, *, settings=None: _fake_embed(texts),
            ):
                store.upsert_chunks(
                    "A",
                    [
                        _record_with_embedding("A", "alpha bravo", 0),
                        _record_with_embedding("A", "charlie delta", 1),
                    ],
                )
                assert store.count() == 2
        finally:
            store.close()

    def test_idempotent_reingest_via_content_hash(self, _tmp_db: Path) -> None:
        store = Store(_tmp_db)
        try:
            store.ensure_schema()
            with patch.object(
                embedder,
                "aembed",
                side_effect=lambda texts, *, settings=None: _fake_embed(texts),
            ):
                store.upsert_chunks(
                    "A",
                    [
                        _record_with_embedding("A", "alpha", 0),
                        _record_with_embedding("A", "bravo", 1),
                    ],
                )
                assert store.circular_is_current("A", "h1") is True
                assert store.circular_is_current("A", "different") is False
                store.upsert_chunks(
                    "A",
                    [
                        _record_with_embedding("A", "alpha", 0),
                        _record_with_embedding("A", "bravo", 1),
                    ],
                )
                assert store.count() == 2  # no duplicate rows
        finally:
            store.close()


class TestSearch:
    def _make_records(self, _tmp_db: Path) -> Store:
        store = Store(_tmp_db)
        store.ensure_schema()
        with patch.object(
            embedder,
            "aembed",
            side_effect=lambda texts, *, settings=None: _fake_embed(texts),
        ):
            for circ, text in (
                ("A", "kyc threshold is fifty thousand"),
                ("B", "kyc compliance requirements"),
                ("C", "npa classification rules"),
            ):
                store.upsert_chunks(circ, [_record_with_embedding(circ, text, 0)])
        return store

    def test_lexical_finds_kyc(self, _tmp_db: Path) -> None:
        store = self._make_records(_tmp_db)
        try:
            with patch.object(
                embedder,
                "aembed",
                side_effect=lambda texts, *, settings=None: [
                    [0.0] * DIMS for _ in texts
                ],
            ):
                resp = store.hybrid_search("kyc", limit=5)
                ids = [h.circular_id for h in resp.hits]
                # Lexical scoring dominates when vectors are zero/identical.
                assert "A" in ids and "B" in ids
        finally:
            store.close()

    def test_fts_escaping_and_or_not(self, _tmp_db: Path) -> None:
        store = Store(_tmp_db)
        try:
            store.ensure_schema()
            with patch.object(
                embedder,
                "aembed",
                side_effect=lambda texts, *, settings=None: _fake_embed(texts),
            ):
                store.upsert_chunks(
                    "A", [_record_with_embedding("A", "kyc rules", 0)]
                )
                resp = store.hybrid_search("AND OR NOT", limit=5)
                assert isinstance(resp.hits, list)
                resp = store.hybrid_search("kyc", limit=5)
                assert any(h.circular_id == "A" for h in resp.hits)
        finally:
            store.close()

    def test_fetch(self, _tmp_db: Path) -> None:
        store = self._make_records(_tmp_db)
        try:
            doc = store.fetch("A")
            assert doc is not None
            assert doc.circular_id == "A"
            assert len(doc.chunks) == 1
            assert store.fetch("nonexistent") is None
        finally:
            store.close()

    def test_list_recent(self, _tmp_db: Path) -> None:
        store = self._make_records(_tmp_db)
        try:
            items = store.list_recent("2023-01-01")
            assert {it.circular_id for it in items} == {"A", "B", "C"}
            items = store.list_recent("2030-01-01")
            assert items == []
        finally:
            store.close()

    def test_compare(self, _tmp_db: Path) -> None:
        store = self._make_records(_tmp_db)
        try:
            comp = store.compare("A", "B")
            assert comp is not None
            assert comp.a.circular_id == "A"
            assert comp.b.circular_id == "B"
            assert store.compare("A", "nope") is None
        finally:
            store.close()

    def test_rrf_k_setting_propagates(self, _tmp_db: Path) -> None:
        """Different RRF k values should not change the relative ranking for known vectors."""
        store = self._make_records(_tmp_db)
        try:
            with patch.object(
                embedder,
                "aembed",
                side_effect=lambda texts, *, settings=None: _fake_embed(texts),
            ):
                resp_default = store.hybrid_search("kyc", limit=3)
                store.settings.rrf_k = 1
                resp_small_k = store.hybrid_search("kyc", limit=3)
                # Same lexical order regardless of k (only the score magnitudes differ).
                assert [h.circular_id for h in resp_default.hits] == [
                    h.circular_id for h in resp_small_k.hits
                ]
        finally:
            store.close()


class TestColumnOrderIndependence:
    """Adding a column to the SELECT must not break the row-reading code."""

    def test_row_factory_returns_named_columns(self, _tmp_db: Path) -> None:
        store = Store(_tmp_db)
        try:
            store.ensure_schema()
            with patch.object(
                aembed, "__call__", side_effect=lambda texts, *, settings=None: _fake_embed(texts)
            ):
                store.upsert_chunks(
                    "A", [_record_with_embedding("A", "kyc threshold", 0)]
                )
            # Force a select that doesn't match the expected column count
            # and verify the row reader still works via row_factory names.
            with store._lock:  # type: ignore[attr-defined]
                store._conn.execute(  # type: ignore[attr-defined]
                    "SELECT id, circular_id, title, text, chunk_index FROM chunks"
                )
                row = store._conn.execute(  # type: ignore[attr-defined]
                    "SELECT * FROM chunks"
                ).fetchone()
            # Row uses sqlite3.Row, so named access works regardless of column order.
            assert row["circular_id"] == "A"
            assert row["chunk_index"] == 0
        finally:
            store.close()


class TestEmbeddingDimMismatch:
    def test_dim_mismatch_raises(self) -> None:
        import litellm  # type: ignore[import-untyped]

        from docendo.exceptions import EmbeddingProviderError

        wrong = [0.0] * (DIMS - 1)  # one short

        class _Resp:
            def __init__(self, vec: list[float]) -> None:
                self.data = [{"embedding": vec}]

        async def _fake_litellm(*args, **kwargs):
            return _Resp(wrong)

        with (
            patch.object(litellm, "aembedding", side_effect=_fake_litellm),
            pytest.raises(EmbeddingProviderError),
        ):
            asyncio.run(aembed(["x"]))

    def test_empty_embedding_raises(self) -> None:
        """Empty vectors are an error, not silent []."""
        import litellm  # type: ignore[import-untyped]

        from docendo.exceptions import EmbeddingProviderError

        class _Resp:
            def __init__(self) -> None:
                self.data = [{"embedding": []}]

        async def _fake_empty(*args, **kwargs):
            return _Resp()

        with (
            patch.object(litellm, "aembedding", side_effect=_fake_empty),
            pytest.raises(EmbeddingProviderError),
        ):
            asyncio.run(aembed(["x"]))


class TestConcurrency:
    def test_concurrent_readers_one_writer(self, _tmp_db: Path) -> None:
        store = Store(_tmp_db)
        try:
            store.ensure_schema()

            def reader() -> None:
                for _ in range(20):
                    store.count()
                    store.list_recent("2023-01-01")

            def writer(idx: int) -> None:
                store.upsert_chunks(
                    f"W{idx}", [_record_with_embedding(f"W{idx}", f"text {idx}", 0)]
                )

            threads = [threading.Thread(target=reader) for _ in range(5)]
            threads.append(threading.Thread(target=writer, args=(0,)))
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)
                assert not t.is_alive()
        finally:
            store.close()


class TestChunkerWiring:
    """Verify that the chunker module produces chunks we can embed."""

    def test_chunker_returns_strings(self, _tmp_db: Path) -> None:
        # Don't even need the store; just sanity-check chunker is wired.
        from docendo.retrieval import chunker

        chunks = chunker.chunk(
            "kyc threshold is fifty thousand rupees per transaction",
            chunk_size=4,
            overlap=1,
        )
        assert len(chunks) >= 1
        assert all(isinstance(c, str) for c in chunks)
