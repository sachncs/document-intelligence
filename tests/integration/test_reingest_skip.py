"""Re-ingestion skip test for the SQLite-backed pipeline."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pypdf
import pytest
from docendo.models import Page, Record


def _write_fake_pdf(path: Path) -> Path:
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=72, height=72)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        writer.write(fh)
    return path


def _fake_read(*args, **kwargs):
    return Record(
        circular_id=kwargs["circular_id"],
        title=kwargs["title"],
        issue_date="2024-01-15",
        topic=kwargs.get("topic", "kyc"),
        source_url=kwargs["source_url"],
        pages=[Page(page_number=1, text="kyc rule", method="text")],
        full_text="kyc rule",
    )


class TestReingestSkip:
    def test_second_run_makes_zero_embedding_calls(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        db = tmp_path / "docendo.sqlite3"
        monkeypatch.setenv("STORE_PATH", str(db))
        monkeypatch.setenv("VECTOR_DIMS", "4")
        monkeypatch.setenv("VECTOR_KEY", "test-key")
        monkeypatch.setenv("VECTOR_BASE", "https://embed.example.com")
        monkeypatch.setenv("VECTOR_MODEL", "Qwen/Qwen3-Embedding-8B")
        monkeypatch.setenv("TOKENIZER_MODEL", "Qwen/Qwen3-Embedding-8B")
        monkeypatch.setenv("CHAT_KEY", "test-key")

        pdf_path = _write_fake_pdf(tmp_path / "raw" / "doc1.pdf")
        fake_doc = MagicMock()
        fake_doc.circular_id = "DOC1"
        fake_doc.title = "Doc One"
        fake_doc.pdf_url = "https://rbi.org.in/doc1"
        fake_doc.topic = "kyc"
        fake_vecs = [[0.5] * 4]

        def _discover(*args, **kwargs):
            yield (fake_doc, pdf_path)

        with (
            patch(
                "docendo.ingestion.ingest.discover",
                side_effect=_discover,
            ),
            patch(
                "docendo.ingestion.ingest.read",
                side_effect=_fake_read,
            ),
            patch(
                "docendo.retrieval.embedder.aembed",
                side_effect=lambda texts, *, settings=None: fake_vecs[: len(texts)],
            ) as embed_mock,
        ):
            from docendo.config import reset_settings_cache
            from docendo.ingestion.ingest import run

            reset_settings_cache()
            first = run(
                raw_dir=tmp_path / "raw",
                chunk_size=8,
                chunk_overlap=2,
            )
            assert first.indexed == 1
            assert first.skipped == 0
            first_call_count = embed_mock.call_count

            second = run(
                raw_dir=tmp_path / "raw",
                chunk_size=8,
                chunk_overlap=2,
            )
            assert second.indexed == 0
            assert second.skipped == 1
            assert embed_mock.call_count == first_call_count, (
                f"Embedding was called {embed_mock.call_count} times on re-run "
                f"(expected no new calls)"
            )
