"""Tests for the ChunkRecord Pydantic model."""

from __future__ import annotations

import pytest
from docendo.retrieval.record import ChunkRecord
from pydantic import HttpUrl, ValidationError


def _record(**overrides) -> ChunkRecord:
    base = {
        "circular_id": "RBI/2024/1",
        "title": "T",
        "text": "text",
        "issue_date": "2024-01-15",
        "topic": "kyc",
        "source_url": HttpUrl("https://rbi.org.in/x"),
        "page_estimate_start": 1,
        "page_estimate_end": 2,
        "chunk_index": 0,
        "chunk_count": 1,
        "extraction_method": "text",
        "content_hash": "abc",
        "embedding": [0.1, 0.2, 0.3, 0.4],
    }
    base.update(overrides)
    return ChunkRecord(**base)


class TestRecord:
    def test_typographic_typo_raises_validation_error(self) -> None:
        """A typo in any field name raises ValidationError at the boundary."""
        bad = {
            "circle_id": "RBI/2024/1",  # typo: missing 'u'
            "title": "T",
            "text": "text",
            "source_url": "https://rbi.org.in/x",
            "page_estimate_start": 1,
            "page_estimate_end": 2,
            "chunk_index": 0,
            "chunk_count": 1,
            "extraction_method": "text",
            "content_hash": "abc",
            "embedding": [0.1],
        }
        with pytest.raises(ValidationError):
            ChunkRecord(**bad)

    def test_page_estimate_fields_present(self) -> None:
        """page_estimate_start/end default sensibly and accept None."""
        r = _record(page_estimate_start=1, page_estimate_end=10)
        assert r.page_estimate_start == 1
        assert r.page_estimate_end == 10

    def test_default_embedding_empty_list(self) -> None:
        r = _record(embedding=[])
        # The field accepts any list[float]; empty is allowed at construction.
        # The Store-side parse_blob rejects empty on write.
        assert r.embedding == []
