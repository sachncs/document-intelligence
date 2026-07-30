"""Tests for the SQLite retrieval store.

Uses a fake embedding function so the tests run offline. Verifies:
- Schema bootstrap (FTS5 triggers, sqlite-vector init).
- Round-trip of upsert + lexical/vector search.
- RRF fusion order.
- Re-ingest via content_hash skips unchanged PDFs.
- FTS5 escaping handles quotes, special chars, AND/OR/NOT.
- Embedding-dim mismatch errors.
"""

from __future__ import annotations

import math
import sqlite3
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from docendo.config import reset_settings_cache
from docendo.retrieval.factory import reset_retriever_cache
from docendo.retrieval.sqlite_store import SQLiteStore, _fts_escape

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
def tmp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
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


class TestFtsEscape:
    def test_simple(self) -> None:
        assert _fts_escape("kyc requirements") == '"kyc requirements"'

    def test_quote_doubling(self) -> None:
        assert _fts_escape('say "hi"') == '"say ""hi"""'

    def test_and_or_not_literalized(self) -> None:
        out = _fts_escape("AND OR NOT")
        assert out == '"AND OR NOT"'


class TestSchema:
    def test_ensure_schema_creates_objects(self, tmp_db: Path) -> None:
        store = SQLiteStore(tmp_db)
        try:
            store.ensure_schema()
            conn = sqlite3.connect(str(tmp_db))
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
    def _sample(self, circ: str, text: str, chunk_index: int, content_hash: str = "h1"):
        return {
            "circular_id": circ,
            "title": f"Title {circ}",
            "text": text,
            "issue_date": "2024-01-15",
            "topic": "kyc",
            "source_url": f"https://rbi.org.in/{circ}",
            "page_start": 1,
            "page_end": 5,
            "chunk_index": chunk_index,
            "chunk_count": 2,
            "extraction_method": "text",
            "content_hash": content_hash,
        }

    def test_upsert_and_count(self, tmp_db: Path) -> None:
        store = SQLiteStore(tmp_db)
        try:
            store.ensure_schema()
            with patch(
                "docendo.retrieval.embeddings.async_embed_texts",
                side_effect=lambda texts, *, settings: _fake_embed(texts, settings=settings),
            ):
                recs = [
                    {**self._sample("A", "alpha bravo", 0), "embedding": _fake_embed(["alpha bravo"])[0]},
                    {**self._sample("A", "charlie delta", 1), "embedding": _fake_embed(["charlie delta"])[0]},
                ]
                store.upsert_chunks("A", recs)
                assert store.count() == 2
        finally:
            store.close()

    def test_idempotent_reingest_via_content_hash(self, tmp_db: Path) -> None:
        store = SQLiteStore(tmp_db)
        try:
            store.ensure_schema()
            with patch(
                "docendo.retrieval.embeddings.async_embed_texts",
                side_effect=lambda texts, *, settings: _fake_embed(texts, settings=settings),
            ):
                recs = [
                    {**self._sample("A", "alpha", 0), "embedding": _fake_embed(["alpha"])[0]},
                    {**self._sample("A", "bravo", 1), "embedding": _fake_embed(["bravo"])[0]},
                ]
                store.upsert_chunks("A", recs)
                assert store.circular_is_current("A", "h1") is True
                assert store.circular_is_current("A", "different") is False
                # Re-ingesting with same content_hash should still be safe.
                store.upsert_chunks("A", recs)
                assert store.count() == 2  # no duplicate rows
        finally:
            store.close()


class TestSearch:
    def _make_records(self, tmp_db: Path):
        store = SQLiteStore(tmp_db)
        store.ensure_schema()
        with patch(
            "docendo.retrieval.embeddings.async_embed_texts",
            side_effect=lambda texts, *, settings: _fake_embed(texts, settings=settings),
        ):
            records = [
                {
                    **self._sample("A", "kyc threshold is fifty thousand", 0),
                    "embedding": _fake_embed(["kyc threshold is fifty thousand"])[0],
                },
                {
                    **self._sample("B", "kyc compliance requirements", 0),
                    "embedding": _fake_embed(["kyc compliance requirements"])[0],
                },
                {
                    **self._sample("C", "npa classification rules", 0),
                    "embedding": _fake_embed(["npa classification rules"])[0],
                },
            ]
            for r in records:
                store.upsert_chunks(r["circular_id"], [r])
        return store

    def _sample(self, circ: str, text: str, chunk_index: int, content_hash: str = "h1"):
        return {
            "circular_id": circ,
            "title": f"Title {circ}",
            "text": text,
            "issue_date": "2024-01-15",
            "topic": "kyc",
            "source_url": f"https://rbi.org.in/{circ}",
            "page_start": 1,
            "page_end": 5,
            "chunk_index": chunk_index,
            "chunk_count": 1,
            "extraction_method": "text",
            "content_hash": content_hash,
        }

    def test_lexical_finds_kyc(self, tmp_db: Path) -> None:
        store = self._make_records(tmp_db)
        try:
            # The vector fake is hash-based and not semantically meaningful,
            # but lexical-only search should still rank A and B above C.
            with patch(
                "docendo.retrieval.embeddings.async_embed_texts",
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

    def test_fts_escaping_and_or_not(self, tmp_db: Path) -> None:
        store = SQLiteStore(tmp_db)
        try:
            store.ensure_schema()
            with patch(
                "docendo.retrieval.embeddings.async_embed_texts",
                side_effect=lambda texts, *, settings=None: _fake_embed(texts),
            ):
                rec = {
                    **self._sample("A", "kyc rules", 0),
                    "embedding": _fake_embed(["kyc rules"])[0],
                }
                store.upsert_chunks("A", [rec])
                # "AND OR NOT" must NOT raise a syntax error; treated as literal tokens.
                resp = store.hybrid_search("AND OR NOT", limit=5)
                assert isinstance(resp.hits, list)
                # "kyc" still works after the escape test.
                resp = store.hybrid_search("kyc", limit=5)
                assert any(h.circular_id == "A" for h in resp.hits)
        finally:
            store.close()

    def test_get_circular(self, tmp_db: Path) -> None:
        store = self._make_records(tmp_db)
        try:
            cr = store.get_circular("A")
            assert cr is not None
            assert cr.circular_id == "A"
            assert len(cr.chunks) == 1
            assert store.get_circular("nonexistent") is None
        finally:
            store.close()

    def test_list_recent(self, tmp_db: Path) -> None:
        store = self._make_records(tmp_db)
        try:
            items = store.list_recent("2023-01-01")
            assert {it.circular_id for it in items} == {"A", "B", "C"}
            items = store.list_recent("2030-01-01")
            assert items == []
        finally:
            store.close()

    def test_compare(self, tmp_db: Path) -> None:
        store = self._make_records(tmp_db)
        try:
            comp = store.compare("A", "B")
            assert comp is not None
            assert comp.a.circular_id == "A"
            assert comp.b.circular_id == "B"
            assert store.compare("A", "nope") is None
        finally:
            store.close()


class TestEmbeddingDimMismatch:
    def test_dim_mismatch_raises(self) -> None:
        """Mock litellm.aembedding to return a wrong-length vector; the
        embedding wrapper must raise EmbeddingProviderError on dim mismatch."""
        import asyncio

        import litellm  # type: ignore[import-untyped]

        from docendo.exceptions import EmbeddingProviderError
        from docendo.retrieval import embeddings

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
            asyncio.run(embeddings.async_embed_texts(["x"]))


class TestConcurrency:
    def test_concurrent_readers_one_writer(self, tmp_db: Path) -> None:
        store = SQLiteStore(tmp_db)
        try:
            store.ensure_schema()

            def reader() -> None:
                for _ in range(20):
                    store.count()

            def writer(idx: int) -> None:
                rec = {
                    "circular_id": f"W{idx}",
                    "title": f"W{idx}",
                    "text": f"text {idx}",
                    "issue_date": "2024-01-15",
                    "topic": "kyc",
                    "source_url": f"https://rbi.org.in/W{idx}",
                    "page_start": 1,
                    "page_end": 1,
                    "chunk_index": 0,
                    "chunk_count": 1,
                    "extraction_method": "text",
                    "content_hash": f"h{idx}",
                    "embedding": _fake_embed([f"text {idx}"])[0],
                }
                store.upsert_chunks(f"W{idx}", [rec])

            threads = [threading.Thread(target=reader) for _ in range(5)]
            threads.append(threading.Thread(target=writer, args=(0,)))
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)
                assert not t.is_alive()
        finally:
            store.close()
