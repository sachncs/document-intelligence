"""Performance budget benchmarks.

All benchmarks skip unless ``RUN_PERF=1`` is set in the environment,
so they never run in the default CI lane.

Re-run with::

    RUN_PERF=1 pytest tests/perf -v

Results are emitted to ``reports/perf.json`` for trend tracking.
"""

import json
import math
import os
import statistics
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from docendo.retrieval.store import Store

DIMS = 8
_RUN_PERF = os.environ.get("RUN_PERF") == "1"


def _normalize(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _fake_embed(texts, *, settings=None):
    return [
        _normalize([((abs(hash(t)) >> (i * 8)) & 0xFF) / 127.5 - 1.0 for i in range(DIMS)])
        for t in texts
    ]


def _populate(store: Store, n: int) -> None:
    """Insert ``n`` small synthetic chunks (one per circular)."""
    from docendo.retrieval.record import ChunkRecord
    from pydantic import HttpUrl

    with patch(
        "docendo.retrieval.embedder.aembed",
        side_effect=lambda texts, *, settings=None: [
            _fake_embed(texts)[0] for _ in texts
        ],
    ):
        import asyncio

        async def _go() -> int:
            inserted = 0
            for i in range(n):
                text = f"circular {i} kyc compliance rules and provisions"
                vec = _fake_embed([text])[0]
                store.upsert_chunks(
                    f"CIRC{i:04d}",
                    [
                        ChunkRecord(
                            circular_id=f"CIRC{i:04d}",
                            title=f"Circular {i}",
                            text=text,
                            issue_date="2024-01-15",
                            topic="kyc",
                            source_url=HttpUrl(f"https://rbi.org.in/C{i}"),
                            page_estimate_start=1,
                            page_estimate_end=1,
                            chunk_index=0,
                            chunk_count=1,
                            extraction_method="text",
                            content_hash=f"h{i}",
                            embedding=vec,
                        )
                    ],
                )
                inserted += 1
            return inserted

        asyncio.run(_go())


def _maybe_write_perf_report(name: str, payload: dict) -> None:
    """Append a benchmark record to ``reports/perf.json`` (best-effort)."""
    try:
        reports_dir = Path("reports")
        reports_dir.mkdir(parents=True, exist_ok=True)
        out = reports_dir / "perf.json"
        data = json.loads(out.read_text()) if out.exists() else {"benchmarks": []}
        data["benchmarks"].append({"name": name, **payload})
        out.write_text(json.dumps(data, indent=2))
    except Exception:
        pass


@pytest.fixture
def _tmp_db(tmp_path: Path):
    return tmp_path / "docendo.sqlite3"


@pytest.mark.perf
@pytest.mark.skipif(not _RUN_PERF, reason="Set RUN_PERF=1 to run benchmarks")
class TestIngestBudget:
    def test_ingest_100_synthetic_chunks_under_5_seconds(self, _tmp_db: Path) -> None:
        store = Store(_tmp_db)
        try:
            store.ensure_schema()
            start = time.perf_counter()
            _populate(store, 100)
            elapsed = time.perf_counter() - start
            _maybe_write_perf_report(
                "ingest_100_chunks",
                {"elapsed_s": elapsed, "chunks": 100},
            )
            assert elapsed < 5.0, f"100-chunk ingest took {elapsed:.2f}s (budget 5s)"
        finally:
            store.close()


@pytest.mark.perf
@pytest.mark.skipif(not _RUN_PERF, reason="Set RUN_PERF=1 to run benchmarks")
class TestSearchLatency:
    def test_hybrid_search_p95_under_100ms(self, _tmp_db: Path) -> None:
        store = Store(_tmp_db)
        try:
            store.ensure_schema()
            _populate(store, 200)
            for _ in range(5):
                with patch(
                    "docendo.retrieval.embedder.aembed",
                    side_effect=lambda texts, *, settings=None: [
                        [0.0] * DIMS for _ in texts
                    ],
                ):
                    store.hybrid_search("kyc", 5)
            samples_ms: list[float] = []
            for _ in range(50):
                with patch(
                    "docendo.retrieval.embedder.aembed",
                    side_effect=lambda texts, *, settings=None: [
                        [0.0] * DIMS for _ in texts
                    ],
                ):
                    start = time.perf_counter()
                    store.hybrid_search("kyc compliance", 5)
                    samples_ms.append((time.perf_counter() - start) * 1000)
            p50 = statistics.median(samples_ms)
            p95 = sorted(samples_ms)[int(len(samples_ms) * 0.95) - 1]
            _maybe_write_perf_report(
                "hybrid_search_latency",
                {"p50_ms": p50, "p95_ms": p95, "samples": len(samples_ms)},
            )
            assert p95 < 100.0, f"p95 {p95:.1f}ms exceeds 100ms budget"
        finally:
            store.close()


@pytest.mark.perf
@pytest.mark.skipif(not _RUN_PERF, reason="Set RUN_PERF=1 to run benchmarks")
class TestReingestSkip:
    def test_reingest_of_unchanged_corpus_under_10_seconds(
        self, _tmp_db: Path
    ) -> None:
        """Re-ingesting the same SQLite file makes zero new embedding calls."""
        store = Store(_tmp_db)
        try:
            store.ensure_schema()
            _populate(store, 50)

            with patch(
                "docendo.retrieval.embedder.aembed",
                side_effect=lambda texts, *, settings=None: [],
            ) as embed_mock:
                start = time.perf_counter()
                for i in range(50):
                    store.circular_is_current(f"CIRC{i:04d}", f"h{i}")
                elapsed = time.perf_counter() - start
            _maybe_write_perf_report(
                "reingest_skip_check",
                {"elapsed_s": elapsed, "chunks": 50, "embedding_calls": embed_mock.call_count},
            )
            assert embed_mock.call_count == 0
            assert elapsed < 10.0, f"skip-check took {elapsed:.2f}s (budget 10s)"
        finally:
            store.close()
