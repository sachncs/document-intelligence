"""Tests for the PDF extraction module.

Mocks vision API and pypdf to keep tests offline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from docendo.exceptions import PDFExtractionError
from docendo.ingestion.pdf import (
    _parse_issue_date,
    extract_pdf,
    extract_text_via_vision,
    render_page_to_png,
)


class TestParseIssueDate:
    def test_dd_mm_yyyy(self) -> None:
        assert _parse_issue_date("Issued on 15/03/2024 by RBI") == "2024-03-15"

    def test_dd_mm_yyyy_dash(self) -> None:
        assert _parse_issue_date("Date: 15-03-2024") == "2024-03-15"

    def test_month_name(self) -> None:
        assert _parse_issue_date("Issued March 15, 2024") == "2024-03-15"

    def test_no_date(self) -> None:
        assert _parse_issue_date("No date here") is None


class TestVisionAPI:
    def test_extract_text_via_vision(self, settings: Any) -> None:
        with patch("docendo.ingestion.pdf.completion") as mock:
            resp = MagicMock()
            resp.choices = [MagicMock()]
            resp.choices[0].message.content = "Extracted text."
            mock.return_value = resp
            text = extract_text_via_vision(b"fake png bytes", settings=settings)
        assert text == "Extracted text."

    def test_extract_text_via_vision_empty_response(self, settings: Any) -> None:
        from docendo.exceptions import VisionAPIError

        with patch("docendo.ingestion.pdf.completion") as mock:
            resp = MagicMock()
            resp.choices = [MagicMock()]
            resp.choices[0].message.content = ""
            mock.return_value = resp
            with pytest.raises(VisionAPIError):
                extract_text_via_vision(b"x", settings=settings)


class TestRenderPage:
    def test_render_page_to_png_file_not_found(self) -> None:
        with pytest.raises(PDFExtractionError):
            render_page_to_png(Path("/no/such/file.pdf"), 1)


class TestExtractPdf:
    def _fake_pdf(self, tmp_path: Path, page_texts: list[str]) -> Path:
        """Create a real PDF with text using pypdf (no mocks needed)."""
        import pypdf

        path = tmp_path / "test.pdf"
        writer = pypdf.PdfWriter()
        for _text in page_texts:
            writer.add_blank_page(width=72, height=72)
        with path.open("wb") as fh:
            writer.write(fh)
        # We can't easily add text to a blank page without reportlab,
        # so we just test the file-not-found path here. The full vision
        # fallback path is exercised in integration tests.
        return path

    def test_extract_missing_file(self, tmp_path: Path, settings: Any) -> None:
        with pytest.raises(PDFExtractionError):
            extract_pdf(
                tmp_path / "does-not-exist.pdf",
                circular_id="x",
                title="x",
                source_url="https://rbi.org.in/x",
                settings=settings,
            )
