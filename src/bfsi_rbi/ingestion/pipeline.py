"""End-to-end ingestion pipeline: scrape → extract → index."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bfsi_rbi.config import Settings, get_settings
from bfsi_rbi.es.client import get_es_client
from bfsi_rbi.es.index import ensure_index
from bfsi_rbi.exceptions import ElasticsearchError
from bfsi_rbi.ingestion.pdf import extract_pdf
from bfsi_rbi.ingestion.rbi_scraper import (
    discover_and_download,
)
from bfsi_rbi.logging import get_logger
from bfsi_rbi.models import ExtractedDocument

logger = get_logger(__name__)


@dataclass
class IngestionReport:
    """Summary of an ingestion run."""

    total_discovered: int = 0
    downloaded: int = 0
    extracted: int = 0
    indexed: int = 0
    failed: list[str] = field(default_factory=list)
    documents: list[ExtractedDocument] = field(default_factory=list)


def _chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Greedy word-boundary chunking."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be in [0, chunk_size)")
    words = text.split()
    if not words:
        return []
    chunks: list[str] = []
    i = 0
    while i < len(words):
        end = min(i + chunk_size, len(words))
        chunks.append(" ".join(words[i:end]))
        if end == len(words):
            break
        i += chunk_size - overlap
    return chunks


def _to_es_doc(doc: ExtractedDocument, chunk_size: int, chunk_overlap: int) -> list[dict[str, Any]]:
    """Convert an ExtractedDocument into ES bulk-ready actions.

    Each chunk is a separate document with a `parent_id` field pointing
    to the parent circular's ID. The first chunk carries the full metadata.
    """
    chunks = _chunk_text(doc.full_text, chunk_size, chunk_overlap)
    if not chunks:
        return []
    bulk: list[dict[str, Any]] = []
    for idx, chunk in enumerate(chunks):
        is_first = idx == 0
        body = {
            "circular_id": doc.circular_id,
            "title": doc.title,
            "text": chunk,
            "semantic_text": chunk,
            "issue_date": doc.issue_date,
            "topic": doc.topic,
            "source_url": str(doc.source_url),
            "page_count": len(doc.pages),
            "extraction_method": "mixed"
            if any(p.method == "vision" for p in doc.pages)
            else "text",
            "chunk_index": idx,
            "chunk_count": len(chunks),
        }
        if not is_first:
            body["title"] = f"{doc.title} (chunk {idx + 1}/{len(chunks)})"
        bulk.append(
            {"index": {"_index": doc.circular_id + "_chunks", "_id": f"{doc.circular_id}_{idx}"}}
        )
        bulk.append(body)
    return bulk


def _bulk_index(bulk_actions: list[dict[str, Any]], es: Any) -> tuple[int, int]:
    """Execute a bulk request and return (success_count, error_count)."""
    try:
        resp = es.bulk(operations=bulk_actions, refresh="wait_for")
    except Exception as exc:
        raise ElasticsearchError(f"Bulk index failed: {exc}") from exc
    ok = sum(1 for item in resp["items"] if next(iter(item.values())).get("status", 500) < 300)
    err = len(resp["items"]) - ok
    return ok, err


def run_ingestion(
    raw_dir: Path | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    max_docs: int | None = None,
    settings: Settings | None = None,
) -> IngestionReport:
    """Run the full ingestion pipeline."""
    settings = settings or get_settings()
    settings.require_elastic()
    raw_dir = Path(raw_dir or settings.data_raw_dir)
    chunk_size = chunk_size or settings.bfsi_chunk_size
    chunk_overlap = chunk_overlap or settings.bfsi_chunk_overlap
    max_docs = max_docs or settings.rbi_fetch_max_docs

    report = IngestionReport()
    es = get_es_client(settings)
    ensure_index(es, settings.bfsi_index_name, recreate=False, settings=settings)

    for doc, path in discover_and_download(raw_dir, max_docs=max_docs, settings=settings):
        report.total_discovered += 1
        report.downloaded += 1
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
            logger.warning("Failed to extract %s: %s", path, exc)
            report.failed.append(str(path))
            continue

        report.extracted += 1
        report.documents.append(extracted)

        bulk_actions = _to_es_doc(extracted, chunk_size, chunk_overlap)
        if not bulk_actions:
            continue
        ok, err = _bulk_index(bulk_actions, es)
        report.indexed += ok
        if err:
            logger.warning("%d chunks failed to index for %s", err, doc.circular_id)
            report.failed.append(f"{doc.circular_id}: {err} chunk errors")

    logger.info(
        "Ingestion complete: discovered=%d, downloaded=%d, extracted=%d, indexed=%d, failed=%d",
        report.total_discovered,
        report.downloaded,
        report.extracted,
        report.indexed,
        len(report.failed),
    )
    return report


__all__ = ["IngestionReport", "run_ingestion"]
