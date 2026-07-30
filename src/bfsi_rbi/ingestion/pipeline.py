"""End-to-end ingestion pipeline: scrape → extract → chunk → embed → store.

The pipeline is backend-neutral except for one call: ``retriever.upsert_chunks``.
Each chunk is embedded once via :func:`bfsi_rbi.retrieval.embeddings.async_embed_texts`,
and the SQLite store receives pre-computed vectors (no SQL/embedding coupling).
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bfsi_rbi.config import Settings, get_settings
from bfsi_rbi.exceptions import StorageError
from bfsi_rbi.ingestion.pdf import extract_pdf
from bfsi_rbi.ingestion.rbi_scraper import discover_and_download
from bfsi_rbi.logging import get_logger
from bfsi_rbi.models import ExtractedDocument
from bfsi_rbi.retrieval.tokenizer import chunk_text

logger = get_logger(__name__)


@dataclass
class IngestionReport:
    """Summary of an ingestion run."""

    total_discovered: int = 0
    downloaded: int = 0
    extracted: int = 0
    indexed: int = 0
    skipped: int = 0
    failed: list[str] = field(default_factory=list)
    documents: list[ExtractedDocument] = field(default_factory=list)


def _content_hash(path: Path) -> str:
    """Return a stable SHA-256 hex digest of the PDF bytes."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _build_chunks(
    extracted: ExtractedDocument,
    content_hash: str,
    chunk_size_tokens: int,
    chunk_overlap_tokens: int,
    settings: Settings,
) -> list[dict[str, Any]]:
    """Convert an ExtractedDocument into backend-neutral chunk records (no embeddings)."""
    if not extracted.full_text.strip():
        return []
    texts = chunk_text(
        extracted.full_text,
        chunk_size=chunk_size_tokens,
        overlap=chunk_overlap_tokens,
        settings=settings,
    )
    if not texts:
        return []
    records: list[dict[Any, Any]] = []
    for idx, text in enumerate(texts):
        records.append(
            {
                "circular_id": extracted.circular_id,
                "title": extracted.title,
                "text": text,
                "issue_date": extracted.issue_date,
                "topic": extracted.topic,
                "source_url": str(extracted.source_url),
                "page_start": 1,
                "page_end": max(1, len(extracted.pages)),
                "chunk_index": idx,
                "chunk_count": len(texts),
                "extraction_method": (
                    "mixed"
                    if any(p.method == "vision" for p in extracted.pages)
                    else "text"
                ),
                "content_hash": content_hash,
            }
        )
    return records


async def _process_one(
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
    from bfsi_rbi.retrieval.embeddings import async_embed_texts

    content_hash = _content_hash(path)
    try:
        if retriever.circular_is_current(doc.circular_id, content_hash):
            logger.info("Skipping %s (content unchanged)", doc.circular_id)
            return 0, True, None
    except Exception as exc:
        logger.warning("Skip-check failed for %s: %s; will re-ingest", doc.circular_id, exc)

    try:
        extracted = extract_pdf(
            path,
            circular_id=doc.circular_id,
            title=doc.title,
            source_url=doc.pdf_url,
            topic=doc.topic,
            settings=settings,
        )
    except Exception as exc:
        return 0, False, f"extract: {exc}"

    chunks = _build_chunks(extracted, content_hash, chunk_size, chunk_overlap, settings)
    if not chunks:
        return 0, False, "no chunks"

    try:
        vectors = await async_embed_texts(
            [str(c["text"]) for c in chunks], settings=settings
        )
    except Exception as exc:
        return 0, False, f"embed: {exc}"

    for c, v in zip(chunks, vectors, strict=True):
        c["embedding"] = v

    try:
        inserted = await asyncio.to_thread(
            retriever.upsert_chunks, doc.circular_id, chunks
        )
    except Exception as exc:
        return 0, False, f"upsert: {exc}"
    return inserted, False, None


def run_ingestion(
    raw_dir: Path | None = None,
    chunk_size_tokens: int | None = None,
    chunk_overlap_tokens: int | None = None,
    max_docs: int | None = None,
    settings: Settings | None = None,
) -> IngestionReport:
    """Run the full ingestion pipeline synchronously."""
    from bfsi_rbi.retrieval.factory import get_retriever

    settings = settings or get_settings()
    settings.require_for_run()
    raw_dir = Path(raw_dir or settings.data_raw_dir)
    chunk_size = chunk_size_tokens or settings.bfsi_chunk_size_tokens
    chunk_overlap = chunk_overlap_tokens or settings.bfsi_chunk_overlap_tokens
    max_docs = max_docs or settings.rbi_fetch_max_docs

    report = IngestionReport()
    retriever = get_retriever(settings)

    try:
        retriever.ensure_schema()
    except Exception as exc:
        raise StorageError(f"Failed to initialize SQLite store: {exc}") from exc

    async def _run_all() -> None:
        for doc, path in discover_and_download(raw_dir, max_docs=max_docs, settings=settings):
            report.total_discovered += 1
            report.downloaded += 1
            inserted, skipped, err = await _process_one(
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

    asyncio.run(_run_all())

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


__all__ = ["IngestionReport", "run_ingestion"]
