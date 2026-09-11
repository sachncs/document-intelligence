"""Tests for the public-site scraper."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from docendo.ingestion import scraper


def _fake_doc(idx: int) -> scraper.Found:
    return scraper.Found(
        circular_id=f"DOC{idx}",
        title=f"Doc {idx}",
        pdf_url=f"https://rbi.example.in/doc{idx}.pdf",
        source_page="https://rbi.example.in/index",
        topic="circular",
    )


def _ok_response() -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.headers = {}
    resp.aclose = MagicMock(side_effect=lambda: _immediate_coro())
    resp.raise_for_status = MagicMock(return_value=None)

    async def aiter_bytes(_chunk_size: int = 8192):
        yield b"%PDF-1.4\n%fake\n%%EOF"

    resp.aiter_bytes = aiter_bytes
    return resp


def _immediate_coro():
    async def _coro():
        return None

    return _coro()


def _throttled_response(retry_after: float) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 429
    resp.headers = {"Retry-After": str(retry_after)}
    resp.aclose = MagicMock(side_effect=lambda: _immediate_coro())
    resp.raise_for_status = MagicMock(return_value=None)
    resp.aiter_bytes = MagicMock()
    return resp


class TestDiscoverConcurrency:
    def test_disover_parallelises_downloads(self, tmp_path: Path) -> None:
        """discover downloads PDFs in parallel under the configured semaphore."""
        import asyncio

        docs = [_fake_doc(i) for i in range(8)]
        active = 0
        peak = 0
        ok = _ok_response()

        async def slow_send(self, _request, **_kwargs):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.05)
            active -= 1
            return ok

        with (
            patch.object(scraper, "scrape", return_value=docs),
            patch.object(scraper.httpx.AsyncClient, "send", new=slow_send),
        ):
            start = time.perf_counter()
            results = list(
                scraper.discover(tmp_path, max_docs=8, concurrency=4)
            )
            elapsed = time.perf_counter() - start

        assert len(results) == 8
        # 8 docs at 50ms each, 4 concurrent -> ~100ms; serial would be ~400ms.
        assert elapsed < 0.3, f"discover took {elapsed:.2f}s (expected ~0.1s)"
        assert peak >= 2, "expected at least 2 concurrent downloads"
        assert peak <= 4, f"concurrency cap exceeded: peak={peak}"

    def test_disover_empty_when_no_links(self, tmp_path: Path) -> None:
        with patch.object(scraper, "scrape", return_value=[]):
            assert list(scraper.discover(tmp_path, max_docs=4)) == []


class TestRetryAfter:
    def test_429_triggers_retry_then_succeeds(self, tmp_path: Path) -> None:
        """A 429 with Retry-After is retried until a 200 response arrives."""

        docs = [_fake_doc(0)]
        attempts = {"n": 0}
        ok = _ok_response()
        throttled = _throttled_response(retry_after=0.01)

        async def send(self, _request, **_kwargs):
            attempts["n"] += 1
            if attempts["n"] == 1:
                return throttled
            return ok

        async def no_sleep(_seconds):
            return None

        with (
            patch.object(scraper, "scrape", return_value=docs),
            patch.object(scraper.httpx.AsyncClient, "send", new=send),
            patch.object(scraper.asyncio, "sleep", new=no_sleep),
        ):
            results = list(
                scraper.discover(tmp_path, max_docs=1, concurrency=1)
            )
        assert attempts["n"] == 2, "should retry exactly once after the 429"
        assert len(results) == 1
