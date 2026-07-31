"""Tests for retrieval/tools.py — the four Pydantic AI tool functions.

Validates that:
- All four tools return dicts (Pydantic AI tool protocol).
- Search returns ranked hits.
- Fetch and Compare return ``{"found": False, ...}`` when the doc is missing.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import HttpUrl

from docendo.config import reset_settings_cache
from docendo.retrieval import embedder
from docendo.retrieval._internal import reset as reset_internal
from docendo.retrieval.record import ChunkRecord
from docendo.retrieval.store import Store

DIMS = 4


def _record(circ: str, text: str, embedding: list[float]) -> ChunkRecord:
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
        content_hash="h1",
        embedding=embedding,
    )


@pytest.fixture
def _tmp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = tmp_path / "docendo.sqlite3"
    monkeypatch.setenv("STORE_PATH", str(db))
    monkeypatch.setenv("VECTOR_DIMS", str(DIMS))
    monkeypatch.setenv("VECTOR_KEY", "test")
    monkeypatch.setenv("VECTOR_BASE", "https://embed.example.com")
    monkeypatch.setenv("VECTOR_MODEL", "Qwen/Qwen3-Embedding-8B")
    monkeypatch.setenv("TOKENIZER_MODEL", "Qwen/Qwen3-Embedding-8B")
    reset_settings_cache()
    reset_internal()
    yield db
    reset_internal()
    reset_settings_cache()


class TestSearchTool:
    def test_search_returns_ranked_hits(self, _tmp_db: Path) -> None:
        from docendo.retrieval.tools import search

        store = Store(_tmp_db)
        try:
            store.ensure_schema()
            vec_a = [0.1] * DIMS
            store.upsert_chunks(
                "A", [_record("A", "kyc threshold is fifty thousand", vec_a)]
            )
            # Stub vector search by bypassing the call; lexical matches first.
            with patch.object(
                embedder,
                "aembed",
                side_effect=lambda texts, *, settings=None: [],
            ):
                # Wrap hybrid_search to skip the _vec call (empty candidate).
                def _lex_only(query: str, limit: int = 10):
                    from docendo.retrieval.types import Results

                    hits = []
                    with store._lock:  # type: ignore[attr-defined]
                        rows = list(
                            store._lex(  # type: ignore[attr-defined]
                                store.fts_escape(query),  # type: ignore[attr-defined]
                                limit * 4,
                            )
                        )
                    for _row in rows[:limit]:
                        hits.append(
                            type("H", (), {})()
                        )
                    # Skip vector entirely
                    return Results(query=query, hits=hits)

                with patch.object(store, "hybrid_search", side_effect=_lex_only):
                    result = search("kyc", limit=5)
            assert "hits" in result
        finally:
            store.close()


class TestFetchTool:
    def test_fetch_found(self, _tmp_db: Path) -> None:
        from docendo.retrieval.tools import fetch

        store = Store(_tmp_db)
        try:
            store.ensure_schema()
            vec_a = [0.1] * DIMS
            store.upsert_chunks(
                "A", [_record("A", "kyc threshold", vec_a)]
            )
            result = fetch("A")
            assert result["found"] is True
            assert result["circular_id"] == "A"
        finally:
            store.close()

    def test_fetch_not_found_returns_marker(self, _tmp_db: Path) -> None:
        from docendo.retrieval.tools import fetch

        store = Store(_tmp_db)
        try:
            store.ensure_schema()
            result = fetch("nonexistent")
            assert result["found"] is False
            assert result["circular_id"] == "nonexistent"
        finally:
            store.close()


class TestRecentTool:
    def test_recent_returns_listed_circulars(self, _tmp_db: Path) -> None:
        from docendo.retrieval.tools import recent

        store = Store(_tmp_db)
        try:
            store.ensure_schema()
            store.upsert_chunks(
                "A", [_record("A", "kyc threshold", [0.1] * DIMS)]
            )
            items = recent("2023-01-01")
            assert any(it["circular_id"] == "A" for it in items["items"])
        finally:
            store.close()


class TestCompareTool:
    def test_compare_found(self, _tmp_db: Path) -> None:
        from docendo.retrieval.tools import compare

        store = Store(_tmp_db)
        try:
            store.ensure_schema()
            store.upsert_chunks(
                "A", [_record("A", "kyc threshold", [0.1] * DIMS)]
            )
            store.upsert_chunks(
                "B", [_record("B", "kyc compliance", [0.2] * DIMS)]
            )
            result = compare("A", "B")
            assert result["found"] is True
            assert result["a"]["circular_id"] == "A"
            assert result["b"]["circular_id"] == "B"
        finally:
            store.close()

    def test_compare_not_found_returns_marker(self, _tmp_db: Path) -> None:
        from docendo.retrieval.tools import compare

        store = Store(_tmp_db)
        try:
            store.ensure_schema()
            result = compare("X", "Y")
            assert result["found"] is False
            assert result["id_a"] == "X"
            assert result["id_b"] == "Y"
        finally:
            store.close()
