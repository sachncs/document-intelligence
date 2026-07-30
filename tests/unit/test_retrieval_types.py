"""Tests for the typed retrieval contract."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from docendo.retrieval.types import (
    CircularResponse,
    CompareInput,
    GetCircularInput,
    HybridSearchInput,
    ListRecentInput,
    RecentItem,
    SearchHit,
    SearchResponse,
)


class TestHybridSearchInput:
    def test_minimal(self) -> None:
        i = HybridSearchInput(query="kyc")
        assert i.limit == 10

    def test_query_too_long(self) -> None:
        with pytest.raises(ValidationError):
            HybridSearchInput(query="x" * 513)

    def test_limit_out_of_range(self) -> None:
        with pytest.raises(ValidationError):
            HybridSearchInput(query="ok", limit=0)
        with pytest.raises(ValidationError):
            HybridSearchInput(query="ok", limit=21)


class TestGetCircularInput:
    def test_valid_id(self) -> None:
        i = GetCircularInput(id="RBI/2023-24/1")
        assert i.id == "RBI/2023-24/1"

    def test_invalid_id_chars(self) -> None:
        with pytest.raises(ValidationError):
            GetCircularInput(id="bad id with spaces")

    def test_id_too_long(self) -> None:
        with pytest.raises(ValidationError):
            GetCircularInput(id="a" * 65)


class TestListRecentInput:
    def test_valid_date(self) -> None:
        i = ListRecentInput(since="2024-01-01")
        assert i.limit == 20

    def test_invalid_date(self) -> None:
        with pytest.raises(ValidationError):
            ListRecentInput(since="2024/01/01")


class TestCompareInput:
    def test_two_valid(self) -> None:
        c = CompareInput(id_a="A", id_b="B")
        assert c.id_a == "A" and c.id_b == "B"


class TestOutputModels:
    def test_search_hit_defaults(self) -> None:
        h = SearchHit(
            circular_id="X",
            title="T",
            text="text",
            chunk_index=0,
            chunk_count=1,
            source_url="https://rbi.org.in/x",
        )
        assert h.score == 0.0
        assert h.extraction_method == "text"

    def test_search_response_roundtrip(self) -> None:
        r = SearchResponse(
            query="kyc",
            hits=[
                SearchHit(
                    circular_id="X",
                    title="T",
                    text="text",
                    chunk_index=0,
                    chunk_count=1,
                    source_url="https://rbi.org.in/x",
                )
            ],
        )
        assert len(r.hits) == 1

    def test_recent_item_minimal(self) -> None:
        r = RecentItem(
            circular_id="X",
            title="T",
            source_url="https://rbi.org.in/x",
        )
        assert r.issue_date is None

    def test_circular_response_chunks(self) -> None:
        cr = CircularResponse(
            circular_id="X",
            title="T",
            source_url="https://rbi.org.in/x",
            chunks=[
                SearchHit(
                    circular_id="X",
                    title="T",
                    text="text",
                    chunk_index=0,
                    chunk_count=1,
                    source_url="https://rbi.org.in/x",
                )
            ],
        )
        assert len(cr.chunks) == 1


class TestPerfBudget:
    """Validation cost should be well under 50 microseconds per call."""

    def test_validates_quickly(self) -> None:
        import time

        n = 1000
        start = time.perf_counter_ns()
        for _ in range(n):
            HybridSearchInput(query="kyc", limit=5)
            GetCircularInput(id="RBI/2024/1")
            ListRecentInput(since="2024-01-01", limit=20)
            CompareInput(id_a="A", id_b="B")
        elapsed_us = (time.perf_counter_ns() - start) / 1000
        per_call_us = elapsed_us / (n * 4)
        assert per_call_us < 50, f"per-call validation cost {per_call_us:.1f}us exceeds 50us budget"
