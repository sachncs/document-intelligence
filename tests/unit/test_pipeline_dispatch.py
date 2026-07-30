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
import pypdf


def _write_fake_pdf(path: Path) -> Path:
    """Write a tiny blank PDF; we don't need real text for these tests."""
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=72, height=72)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        writer.write(fh)
    return path


def _fake_record(*args, **kwargs):
    """Return a small fake Record."""
    from docendo.models import Page, Record

    return Record(
        circular_id=kwargs["circular_id"],
        title=kwargs["title"],
        issue_date="2024-01-15",
        topic=kwargs.get("topic", "kyc"),
        source_url=kwargs["source_url"],
        pages=[Page(page_number=1, text="kyc threshold fifty thousand", method="text")],
        full_text="kyc threshold fifty thousand",
    )


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = tmp_path / "docendo.sqlite3"
    monkeypatch.setenv("STORE_PATH", str(db))
    monkeypatch.setenv("VECTOR_DIMS", "4")
    monkeypatch.setenv("VECTOR_KEY", "test-key")
    monkeypatch.setenv("VECTOR_BASE", "https://embed.example.com")
    monkeypatch.setenv("VECTOR_MODEL", "Qwen/Qwen3-Embedding-8B")
    monkeypatch.setenv("TOKENIZER_MODEL", "Qwen/Qwen3-Embedding-8B")
    monkeypatch.setenv("CHAT_KEY", "test-key")
    return tmp_path


class TestPipelineDispatch:
    def test_routes_to_sqlite_with_embeddings(self, env: Path) -> None:
        from docendo.config import reset_settings_cache
        from docendo.ingestion.ingest import run
        from docendo.retrieval import embedder

        pdf_path = _write_fake_pdf(env / "raw" / "doc1.pdf")
        fake_doc = MagicMock()
        fake_doc.circular_id = "DOC1"
        fake_doc.title = "Doc One"
        fake_doc.pdf_url = "https://rbi.org.in/doc1"
        fake_doc.topic = "kyc"
        fake_vecs = [[0.5] * 4]

        def _discover(*args, **kwargs):
            yield (fake_doc, pdf_path)

        reset_settings_cache()
        with (
            patch(
                "docendo.ingestion.ingest.discover",
                side_effect=_discover,
            ),
            patch(
                "docendo.ingestion.ingest.read",
                side_effect=_fake_record,
            ),
            patch.object(
                embedder, "aembed",
                side_effect=lambda texts, *, settings=None: fake_vecs[: len(texts)],
            ),
        ):
            report = run(
                raw_dir=env / "raw",
                chunk_size=8,
                chunk_overlap=2,
                settings=None,
            )
        assert report.total_discovered == 1
        assert report.downloaded == 1
        assert report.extracted == 1
        assert report.indexed == 1
        assert report.skipped == 0
        assert report.failed == []

    def test_skips_unchanged_content_hash(self, env: Path) -> None:
        from docendo.config import reset_settings_cache
        from docendo.ingestion.ingest import run
        from docendo.retrieval import embedder

        pdf_path = _write_fake_pdf(env / "raw" / "doc1.pdf")
        fake_doc = MagicMock()
        fake_doc.circular_id = "DOC1"
        fake_doc.title = "Doc One"
        fake_doc.pdf_url = "https://rbi.org.in/doc1"
        fake_doc.topic = "kyc"
        fake_vecs = [[0.5] * 4]

        def _discover(*args, **kwargs):
            yield (fake_doc, pdf_path)

        reset_settings_cache()
        with (
            patch(
                "docendo.ingestion.ingest.discover",
                side_effect=_discover,
            ),
            patch(
                "docendo.ingestion.ingest.read",
                side_effect=_fake_record,
            ),
            patch.object(
                embedder, "aembed",
                side_effect=lambda texts, *, settings=None: fake_vecs[: len(texts)],
            ),
        ):
            first = run(
                raw_dir=env / "raw",
                chunk_size=8,
                chunk_overlap=2,
            )
            assert first.indexed == 1
            assert first.skipped == 0

            second = run(
                raw_dir=env / "raw",
                chunk_size=8,
                chunk_overlap=2,
            )
            assert second.indexed == 0
            assert second.skipped == 1
