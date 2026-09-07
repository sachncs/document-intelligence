"""Tests that typed exceptions propagate, not bare Exception."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest
from docendo.config import reset_settings_cache
from docendo.exceptions import (
    EmbeddingProviderError,
    PDFExtractionError,
    ScrapingError,
    StorageError,
)
from docendo.ingestion import ingest
from docendo.ingestion.reader import read
from docendo.retrieval import embedder
from docendo.retrieval._internal import reset as reset_internal
from docendo.retrieval.store import parse_blob


class TestTypedExceptions:
    def test_empty_embedding_raises_typed(self, monkeypatch) -> None:
        """embedder.aembed raises EmbeddingProviderError on empty vector."""
        import litellm  # type: ignore[import-untyped]

        class FakeResp:

            def __getitem__(self, key):
                return getattr(self, key)
            def __init__(self) -> None:
                self.data = [{"embedding": []}]

        async def _fake(*args, **kwargs):
            return FakeResp()

        monkeypatch.setenv("VECTOR_KEY", "test")
        monkeypatch.setenv("VECTOR_BASE", "https://embed.example.com")
        monkeypatch.setenv("VECTOR_DIMS", "4")
        reset_settings_cache()
        try:
            with (
                patch.object(litellm, "aembedding", side_effect=_fake),
                pytest.raises(EmbeddingProviderError),
            ):
                asyncio.run(embedder.aembed(["x"]))
        finally:
            embedder.reset()
            reset_settings_cache()

    def test_parse_blob_empty_raises_storage(self) -> None:
        with pytest.raises(StorageError):
            parse_blob([])

    def test_read_missing_file_raises_typed(self, tmp_path: Path) -> None:
        from docendo.config import Settings

        s = Settings()
        s.chat_key = "test"  # avoid require_llm
        with pytest.raises((PDFExtractionError, ScrapingError, OSError)):
            read(
                tmp_path / "nope.pdf",
                circular_id="X",
                title="X",
                source_url="https://rbi.org.in/x",
                settings=s,
            )


class TestIngestRejectsOnEmbeddingError:
    def test_failed_embedding_marks_doc_failed(self, tmp_path: Path, monkeypatch) -> None:
        """If aembed raises, the document is added to report.failed."""
        monkeypatch.setenv("STORE_PATH", str(tmp_path / "docendo.sqlite3"))
        monkeypatch.setenv("VECTOR_DIMS", "4")
        monkeypatch.setenv("VECTOR_KEY", "test")
        monkeypatch.setenv("VECTOR_BASE", "https://embed.example.com")
        monkeypatch.setenv("VECTOR_MODEL", "Qwen/Qwen3-Embedding-8B")
        monkeypatch.setenv("TOKENIZER_MODEL", "Qwen/Qwen3-Embedding-8B")
        monkeypatch.setenv("CHAT_KEY", "test")
        reset_settings_cache()
        reset_internal()

        try:
            import pypdf

            pdf_path = tmp_path / "raw" / "doc1.pdf"
            pdf_path.parent.mkdir(parents=True, exist_ok=True)
            writer = pypdf.PdfWriter()
            writer.add_blank_page(width=72, height=72)
            with pdf_path.open("wb") as fh:
                writer.write(fh)

            from unittest.mock import MagicMock

            from docendo.models import Page, Record

            fake_doc = MagicMock()
            fake_doc.circular_id = "DOC1"
            fake_doc.title = "Doc One"
            fake_doc.pdf_url = "https://rbi.org.in/doc1"
            fake_doc.topic = "kyc"

            def _discover(*args, **kwargs):
                yield (fake_doc, pdf_path)

            def _read(*args, **kwargs):
                return Record(
                    circular_id="DOC1",
                    title="Doc One",
                    issue_date="2024-01-15",
                    topic="kyc",
                    source_url=kwargs["source_url"],
                    pages=[Page(page_number=1, text="hello", method="text")],
                    full_text="hello",
                )

            async def _embed_fail(texts, *, settings=None):
                raise EmbeddingProviderError("provider down")

            with (
                patch("docendo.ingestion.ingest.discover", side_effect=_discover),
                patch("docendo.ingestion.ingest.read", side_effect=_read),
                patch.object(embedder, "aembed", side_effect=_embed_fail),
            ):
                report = ingest.run(
                    raw_dir=tmp_path / "raw",
                    chunk_size=8,
                    chunk_overlap=2,
                )
            assert report.failed  # the doc is in the failed list
            assert report.indexed == 0
        finally:
            reset_internal()
            reset_settings_cache()
