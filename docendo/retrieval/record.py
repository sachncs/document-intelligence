"""Typed chunk record.

Each row written to ``chunks`` and indexed for retrieval is described by
``ChunkRecord``. Defined as a Pydantic model so any typo in
``ingest.build_records()`` fails at the boundary instead of silently writing
``None`` into a SQLite column.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, HttpUrl


class ChunkRecord(BaseModel):
    """One chunk of one circular, ready for upsert."""

    circular_id: str
    title: str
    text: str
    issue_date: str | None = None
    topic: str | None = None
    source_url: HttpUrl
    page_estimate_start: int = Field(
        default=1,
        description=(
            "Document-level estimate of the first page the chunk may touch. "
            "Not a per-chunk page mapping; do not cite in RAG answers."
        ),
    )
    page_estimate_end: int = Field(
        default=1,
        description="Document-level estimate of the last page the chunk may touch.",
    )
    chunk_index: int
    chunk_count: int
    extraction_method: str = "text"
    content_hash: str
    embedding: list[float]


__all__ = ["ChunkRecord"]
