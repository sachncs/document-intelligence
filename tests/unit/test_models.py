"""Tests for Pydantic models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from bfsi_rbi.models import Citation, ExtractedDocument, ExtractedPage, RBIAnswer


class TestCitation:
    def test_valid(self) -> None:
        c = Citation(
            circular_id="RBI/2023-24/123",
            circular_title="KYC Amendment",
            excerpt="KYC must be updated annually.",
            source_url="https://rbi.org.in/scripts/Notification.aspx?Id=123",
            relevance="Sets the KYC update frequency.",
        )
        assert c.circular_id == "RBI/2023-24/123"

    def test_excerpt_too_long(self) -> None:
        with pytest.raises(ValidationError):
            Citation(
                circular_id="X",
                circular_title="X",
                excerpt="x" * 500,
                source_url="https://rbi.org.in/x",
                relevance="x",
            )


class TestRBIAnswer:
    def test_default_citations(self) -> None:
        a = RBIAnswer(answer="Refused.", confidence="low", notes="Out of scope.")
        assert a.citations == []

    def test_confidence_must_be_literal(self) -> None:
        with pytest.raises(ValidationError):
            RBIAnswer(answer="x", confidence="maybe")  # type: ignore[arg-type]


class TestExtractedDocument:
    def test_full_text_concat(self) -> None:
        doc = ExtractedDocument(
            circular_id="A",
            title="T",
            source_url="https://rbi.org.in/a",
            pages=[
                ExtractedPage(page_number=1, text="hello", method="text"),
                ExtractedPage(page_number=2, text="world", method="vision"),
            ],
            full_text="",
        )
        assert "hello" in doc.full_text and "world" in doc.full_text
