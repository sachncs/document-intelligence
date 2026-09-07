"""Tests for the PDF extraction module.

Mocks vision API and pypdf to keep tests offline.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from docendo.exceptions import PDFExtractionError
from docendo.ingestion.reader import parse_date, read, read_page, render_page


class TestParseDate:
    def test_dd_mm_yyyy(self) -> None:
        assert parse_date("Issued on 15/03/2024 by RBI") == "2024-03-15"

    def test_dd_mm_yyyy_dash(self) -> None:
        assert parse_date("Date: 15-03-2024") == "2024-03-15"

    def test_month_name(self) -> None:
        assert parse_date("Issued March 15, 2024") == "2024-03-15"

    def test_no_date(self) -> None:
        assert parse_date("No date here") is None


class TestVisionAPI:
    def test_read_page(self, settings) -> None:
        with patch("docendo.ingestion.reader.completion") as mock:
            resp = MagicMock()
            resp.choices = [MagicMock()]
            resp.choices[0].message.content = "Extracted text."
            mock.return_value = resp
            text = read_page(b"fake png bytes", settings=settings)
        assert text == "Extracted text."

    def test_read_page_empty_response(self, settings) -> None:
        from docendo.exceptions import VisionAPIError

        with patch("docendo.ingestion.reader.completion") as mock:
            resp = MagicMock()
            resp.choices = [MagicMock()]
            resp.choices[0].message.content = ""
            mock.return_value = resp
            with pytest.raises(VisionAPIError):
                read_page(b"x", settings=settings)


class TestRenderPage:
    def test_render_page_file_not_found(self) -> None:
        with pytest.raises(PDFExtractionError):
            render_page(Path("/no/such/file.pdf"), 1)


class TestRead:
    def _fake_pdf(self, tmp_path: Path) -> Path:
        import pypdf

        path = tmp_path / "test.pdf"
        writer = pypdf.PdfWriter()
        writer.add_blank_page(width=72, height=72)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as fh:
            writer.write(fh)
        return path

    def test_read_missing_file(self, tmp_path: Path, settings) -> None:
        with pytest.raises(PDFExtractionError):
            read(
                tmp_path / "does-not-exist.pdf",
                circular_id="x",
                title="x",
                source_url="https://rbi.org.in/x",
                settings=settings,
            )
