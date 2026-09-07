"""Retrieval subsystem: typed contracts and Protocol."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field, HttpUrl

# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------


class Hit(BaseModel):
    """A single ranked chunk returned by hybrid search."""

    circular_id: str
    title: str
    text: str
    chunk_index: int
    chunk_count: int
    issue_date: str | None = None
    topic: str | None = None
    source_url: HttpUrl
    page_estimate_start: int | None = None
    page_estimate_end: int | None = None
    extraction_method: str = "text"
    score: float = Field(default=0.0, description="RRF fused score.")


class Results(BaseModel):
    """The response from a hybrid_search call."""

    query: str
    hits: list[Hit]


class Document(BaseModel):
    """All chunks of one circular, in order."""

    circular_id: str
    title: str
    issue_date: str | None = None
    topic: str | None = None
    source_url: HttpUrl
    chunks: list[Hit]


class Listing(BaseModel):
    """A first-chunk row for the list_recent tool."""

    circular_id: str
    title: str
    issue_date: str | None = None
    topic: str | None = None
    source_url: HttpUrl


class PairResult(BaseModel):
    """Side-by-side comparison of two circulars."""

    a: Document
    b: Document


# ---------------------------------------------------------------------------
# Input models (hard caps live here)
# ---------------------------------------------------------------------------


class Query(BaseModel):
    """Inputs to the hybrid_search tool."""

    query: str = Field(min_length=1, max_length=512, description="Natural-language query.")
    limit: int = Field(default=10, ge=1, le=20, description="Max hits to return.")


ID_PATTERN = r"^[A-Za-z0-9._:/+\-]+$"


class Lookup(BaseModel):
    """Inputs to the get_circular tool."""

    id: str = Field(
        min_length=1,
        max_length=64,
        pattern=ID_PATTERN,
        description="Circular ID (alphanumerics, dot, slash, underscore, colon, plus, hyphen).",
    )


class Recent(BaseModel):
    """Inputs to the list_recent tool."""

    since: str = Field(
        min_length=10,
        max_length=10,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="ISO date (YYYY-MM-DD).",
    )
    limit: int = Field(default=20, ge=1, le=20)
    include_unknown_date: bool = Field(
        default=False,
        description="If True, include circulars whose issue_date failed to parse.",
    )


class Pair(BaseModel):
    """Inputs to the compare_circulars tool."""

    id_a: str = Field(min_length=1, max_length=64, pattern=ID_PATTERN)
    id_b: str = Field(min_length=1, max_length=64, pattern=ID_PATTERN)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class Retriever(Protocol):
    """The retrieval contract shared by every backend."""

    def ensure_schema(self) -> None:
        """Create tables, indexes, FTS5 virtual table, triggers, and metadata."""

    def upsert_chunks(self, circular_id: str, records: list[Any]) -> int:
        """Replace existing chunks for ``circular_id`` with ``records``.

        Returns the number of chunk rows inserted.
        """

    def circular_is_current(self, circular_id: str, content_hash: str) -> bool:
        """Return True if the stored content_hash for ``circular_id`` matches."""

    def count(self) -> int:
        """Return the total number of chunks stored."""

    def hybrid_search(self, query: str, limit: int = 10) -> Results:
        """Lexical + vector search, fused via RRF."""

    def fetch(self, circular_id: str) -> Document | None:
        """Return all chunks of a circular in order, or None if missing."""

    def list_recent(
        self, since: str, limit: int = 20, include_unknown_date: bool = False
    ) -> list[Listing]:
        """Return first-chunk rows for circulars issued on/after ``since``."""

    def compare(self, id_a: str, id_b: str) -> PairResult | None:
        """Return side-by-side comparison or None if either side is missing."""

    def optimize(self) -> None:
        """Run PRAGMA optimize after bulk insert."""


__all__ = [
    "Document",
    "Hit",
    "Listing",
    "Lookup",
    "Pair",
    "PairResult",
    "Query",
    "Recent",
    "Results",
    "Retriever",
]
