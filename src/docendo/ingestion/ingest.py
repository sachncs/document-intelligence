"""End-to-end ingestion pipeline: scrape -> extract -> chunk -> embed -> store.

The pipeline is backend-neutral except for one call: ``retriever.upsert_chunks``.
Each chunk is embedded once via :func:`docendo.retrieval.embedder.aembed`,
and the SQLite store receives typed ``ChunkRecord`` objects.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from docendo.config import Settings, get_settings
from docendo.exceptions import (
    EmbeddingProviderError,
    ScrapingError,
    StorageError,
    VisionAPIError,
)
from docendo.ingestion.reader import read
from docendo.ingestion.scraper import discover
from docendo.logging import get_logger
from docendo.models import Record
from docendo.retrieval.chunker import chunk
from docendo.retrieval.record import ChunkRecord

logger = get_logger(__name__)


@dataclass
class Report:
    """Summary of an ingestion run."""

    total_discovered: int = 0
    downloaded: int = 0
    extracted: int = 0
    indexed: int = 0
    skipped: int = 0
    failed: list[str] = field(default_factory=list)
    documents: list[Record] = field(default_factory=list)


def hash_pdf(path: Path) -> str:
    """Return a stable SHA-256 hex digest of the PDF bytes."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def build_records(
    extracted: Record,
    content_hash: str,
    chunk_size: int,
    chunk_overlap: int,
    settings: Settings,
) -> list[ChunkRecord]:
    """Convert an extracted document into typed ``ChunkRecord`` objects.

    Page estimates are document-level (page 1 to N for every chunk);
    they are not per-chunk page provenance. See ``ChunkRecord`` docstring.
    """
    if not extracted.full_text.strip():
        return []
    texts = chunk(
        extracted.full_text,
        chunk_size=chunk_size,
        overlap=chunk_overlap,
        settings=settings,
    )
    if not texts:
        return []
    page_count = max(1, len(extracted.pages))
    return [
        ChunkRecord(
            circular_id=extracted.circular_id,
            title=extracted.title,
            text=text,
            issue_date=extracted.issue_date,
            topic=extracted.topic,
            source_url=extracted.source_url,
            page_estimate_start=1,
            page_estimate_end=page_count,
            chunk_index=idx,
            chunk_count=len(texts),
            extraction_method=(
                "mixed"
                if any(p.method == "vision" for p in extracted.pages)
                else "text"
            ),
            content_hash=content_hash,
            embedding=[],  # filled by _process_one after embedding
        )
        for idx, text in enumerate(texts)
    ]


async def process_one(
    retriever: Any,
    doc: Any,
    path: Path,
    chunk_size: int,
    chunk_overlap: int,
    settings: Settings,
) -> tuple[int, bool, str | None]:
    """Process one PDF: extract, chunk, embed, upsert.

    Returns (inserted, skipped, error_message_or_none).
    """
    from docendo.retrieval.embedder import aembed

    content_hash = hash_pdf(path)
    try:
        if retriever.circular_is_current(doc.circular_id, content_hash):
            logger.info("Skipping %s (content unchanged)", doc.circular_id)
            return 0, True, None
    except StorageError as exc:
        logger.warning("Skip-check failed for %s: %s; will re-ingest", doc.circular_id, exc)

    try:
        extracted = read(
            path,
            circular_id=doc.circular_id,
            title=doc.title,
            source_url=doc.pdf_url,
            topic=doc.topic,
            settings=settings,
        )
    except (ScrapingError, VisionAPIError) as exc:
        return 0, False, f"extract: {exc}"

    chunks = build_records(extracted, content_hash, chunk_size, chunk_overlap, settings)
    if not chunks:
        return 0, False, "no chunks"

    try:
        vectors = await aembed([c.text for c in chunks], settings=settings)
    except EmbeddingProviderError as exc:
        return 0, False, f"embed: {exc}"

    for c, v in zip(chunks, vectors, strict=True):
        c.embedding = v

    try:
        inserted = await asyncio.to_thread(
            retriever.upsert_chunks, doc.circular_id, chunks
        )
    except StorageError as exc:
        return 0, False, f"upsert: {exc}"
    return inserted, False, None


def run(
    raw_dir: Path | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    max_docs: int | None = None,
    settings: Settings | None = None,
) -> Report:
    """Run the full ingestion pipeline synchronously."""
    from docendo.retrieval._internal import get

    settings = settings or get_settings()
    settings.require_for_run()
    raw_dir = Path(raw_dir or settings.data_raw_dir)
    chunk_size = chunk_size or settings.chunk_size
    chunk_overlap = chunk_overlap or settings.chunk_overlap
    max_docs = max_docs or settings.fetch_max_docs

    report = Report()
    retriever = get(settings)

    try:
        retriever.ensure_schema()
    except StorageError as exc:
        raise StorageError(f"Failed to initialize SQLite store: {exc}") from exc

    async def run_all() -> None:
        for doc, path in discover(raw_dir, max_docs=max_docs, settings=settings):
            report.total_discovered += 1
            report.downloaded += 1
            inserted, skipped, err = await process_one(
                retriever, doc, path, chunk_size, chunk_overlap, settings
            )
            if err is not None:
                logger.warning("Failed to process %s: %s", doc.circular_id, err)
                report.failed.append(f"{doc.circular_id}: {err}")
                continue
            if skipped:
                report.skipped += 1
            else:
                report.extracted += 1
                report.indexed += inserted

    asyncio.run(run_all())

    with contextlib.suppress(Exception):
        retriever.optimize()

    logger.info(
        "Ingestion complete: discovered=%d, downloaded=%d, extracted=%d, "
        "indexed=%d, skipped=%d, failed=%d",
        report.total_discovered,
        report.downloaded,
        report.extracted,
        report.indexed,
        report.skipped,
        len(report.failed),
    )
    return report


__all__ = ["Report", "build_records", "hash_pdf", "process_one", "run"]
