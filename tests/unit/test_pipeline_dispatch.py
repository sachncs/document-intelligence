"""Tests for the ingestion pipeline dispatch.

Verifies that the pipeline:
- Computes embeddings via LiteLLM.
- Calls upsert_chunks with pre-computed embeddings.
- Skips PDFs whose content_hash is unchanged.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _write_fake_pdf(path: Path) -> Path:
    """Write a tiny blank PDF; we don't need real text for these tests."""
    import pypdf

    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=72, height=72)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        writer.write(fh)
    return path


def _fake_extract_pdf(*args, **kwargs):
    """Return a small fake ExtractedDocument."""
    from docendo.models import ExtractedDocument, ExtractedPage

    return ExtractedDocument(
        circular_id=kwargs["circular_id"],
        title=kwargs["title"],
        issue_date="2024-01-15",
        topic=kwargs.get("topic", "kyc"),
        source_url=kwargs["source_url"],
        pages=[ExtractedPage(page_number=1, text="kyc threshold fifty thousand", method="text")],
        full_text="kyc threshold fifty thousand",
    )


class TestPipelineDispatch:
    def test_routes_to_sqlite_with_embeddings(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        db = tmp_path / "rbi.sqlite3"
        monkeypatch.setenv("BFSI_SQLITE_PATH", str(db))
        monkeypatch.setenv("BFSI_EMBEDDING_DIMS", "4")
        monkeypatch.setenv("BFSI_EMBEDDING_API_KEY", "test-key")
        monkeypatch.setenv("BFSI_EMBEDDING_API_BASE", "https://embed.example.com")
        monkeypatch.setenv("BFSI_EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-8B")
        monkeypatch.setenv("BFSI_TOKENIZER_MODEL", "Qwen/Qwen3-Embedding-8B")
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

        pdf_path = _write_fake_pdf(tmp_path / "raw" / "doc1.pdf")
        fake_doc = MagicMock()
        fake_doc.circular_id = "DOC1"
        fake_doc.title = "Doc One"
        fake_doc.pdf_url = "https://rbi.org.in/doc1"
        fake_doc.topic = "kyc"

        # Fake embeddings: 4-dim unit vectors.
        fake_vecs = [[0.5, 0.5, 0.5, 0.5]]

        with (
            patch(
                "docendo.ingestion.ingest.discover_and_download",
                return_value=iter([(fake_doc, pdf_path)]),
            ),
            patch(
                "docendo.ingestion.ingest.extract_pdf",
                side_effect=_fake_extract_pdf,
            ),
            patch(
                "docendo.retrieval.embedder.async_embed_texts",
                side_effect=lambda texts, *, settings=None: fake_vecs[: len(texts)],
            ),
        ):
            from docendo.config import reset_settings_cache
            from docendo.ingestion.ingest import run_ingestion

            reset_settings_cache()
            report = run_ingestion(
                raw_dir=tmp_path / "raw",
                chunk_size_tokens=8,
                chunk_overlap_tokens=2,
                settings=None,
            )
        assert report.total_discovered == 1
        assert report.downloaded == 1
        assert report.extracted == 1
        assert report.indexed == 1
        assert report.skipped == 0
        assert report.failed == []

    def test_skips_unchanged_content_hash(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        db = tmp_path / "rbi.sqlite3"
        monkeypatch.setenv("BFSI_SQLITE_PATH", str(db))
        monkeypatch.setenv("BFSI_EMBEDDING_DIMS", "4")
        monkeypatch.setenv("BFSI_EMBEDDING_API_KEY", "test-key")
        monkeypatch.setenv("BFSI_EMBEDDING_API_BASE", "https://embed.example.com")
        monkeypatch.setenv("BFSI_EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-8B")
        monkeypatch.setenv("BFSI_TOKENIZER_MODEL", "Qwen/Qwen3-Embedding-8B")
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

        pdf_path = _write_fake_pdf(tmp_path / "raw" / "doc1.pdf")
        fake_doc = MagicMock()
        fake_doc.circular_id = "DOC1"
        fake_doc.title = "Doc One"
        fake_doc.pdf_url = "https://rbi.org.in/doc1"
        fake_doc.topic = "kyc"
        fake_vecs = [[0.5, 0.5, 0.5, 0.5]]

        # Fresh iter per call to discover_and_download.
        def _discover(*args, **kwargs):
            yield (fake_doc, pdf_path)

        with (
            patch(
                "docendo.ingestion.ingest.discover_and_download",
                side_effect=_discover,
            ),
            patch(
                "docendo.ingestion.ingest.extract_pdf",
                side_effect=_fake_extract_pdf,
            ),
            patch(
                "docendo.retrieval.embedder.async_embed_texts",
                side_effect=lambda texts, *, settings=None: fake_vecs[: len(texts)],
            ),
        ):
            from docendo.config import reset_settings_cache
            from docendo.ingestion.ingest import run_ingestion

            reset_settings_cache()
            first = run_ingestion(
                raw_dir=tmp_path / "raw",
                chunk_size_tokens=8,
                chunk_overlap_tokens=2,
            )
            assert first.indexed == 1
            assert first.skipped == 0

            # Second run with same PDF -> content_hash matches, skipped.
            second = run_ingestion(
                raw_dir=tmp_path / "raw",
                chunk_size_tokens=8,
                chunk_overlap_tokens=2,
            )
            assert second.indexed == 0
            assert second.skipped == 1
