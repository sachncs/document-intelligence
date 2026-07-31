"""Tests for the typed retrieval contract."""

from __future__ import annotations

import time

import pytest
from docendo.retrieval.types import (
    Document,
    Hit,
    Listing,
    Lookup,
    Pair,
    Query,
    Recent,
    Results,
)
from pydantic import ValidationError


class TestQuery:
    def test_minimal(self) -> None:
        i = Query(query="kyc")
        assert i.limit == 10

    def test_query_too_long(self) -> None:
        with pytest.raises(ValidationError):
            Query(query="x" * 513)

    def test_limit_out_of_range(self) -> None:
        with pytest.raises(ValidationError):
            Query(query="ok", limit=0)
        with pytest.raises(ValidationError):
            Query(query="ok", limit=21)


class TestLookup:
    def test_valid_id(self) -> None:
        i = Lookup(id="RBI/2023-24/1")
        assert i.id == "RBI/2023-24/1"

    def test_invalid_id_chars(self) -> None:
        with pytest.raises(ValidationError):
            Lookup(id="bad id with spaces")

    def test_id_too_long(self) -> None:
        with pytest.raises(ValidationError):
            Lookup(id="a" * 65)


class TestRecent:
    def test_valid_date(self) -> None:
        i = Recent(since="2024-01-01")
        assert i.limit == 20
        assert i.include_unknown_date is False

    def test_invalid_date(self) -> None:
        with pytest.raises(ValidationError):
            Recent(since="2024/01/01")


class TestPair:
    def test_two_valid(self) -> None:
        c = Pair(id_a="A", id_b="B")
        assert c.id_a == "A" and c.id_b == "B"


class TestOutputModels:
    def test_hit_defaults(self) -> None:
        h = Hit(
            circular_id="X",
            title="T",
            text="text",
            chunk_index=0,
            chunk_count=1,
            source_url="https://rbi.org.in/x",
        )
        assert h.score == 0.0
        assert h.extraction_method == "text"
        # New page-estimate fields default sensibly.
        assert h.page_estimate_start is None
        assert h.page_estimate_end is None

    def test_results_roundtrip(self) -> None:
        r = Results(
            query="kyc",
            hits=[
                Hit(
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

    def test_listing_minimal(self) -> None:
        r = Listing(
            circular_id="X",
            title="T",
            source_url="https://rbi.org.in/x",
        )
        assert r.issue_date is None

    def test_document_chunks(self) -> None:
        cr = Document(
            circular_id="X",
            title="T",
            source_url="https://rbi.org.in/x",
            chunks=[
                Hit(
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
        n = 1000
        start = time.perf_counter_ns()
        for _ in range(n):
            Query(query="kyc", limit=5)
            Lookup(id="RBI/2024/1")
            Recent(since="2024-01-01", limit=20)
            Pair(id_a="A", id_b="B")
        elapsed_us = (time.perf_counter_ns() - start) / 1000
        per_call_us = elapsed_us / (n * 4)
        assert per_call_us < 50, f"per-call validation cost {per_call_us:.1f}us exceeds 50us budget"
