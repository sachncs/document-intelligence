# Performance

This page documents the performance budgets for `docendo v0.2.0` and how
to re-run the benchmark suite.

## Budgets

| Benchmark | Budget | Notes |
|---|---|---|
| 100-chunk synthetic ingest | < 5 s | Local-only; embedding API mocked. |
| `hybrid_search` p95 latency | < 100 ms | Warm cache, 200 chunks, mocked embedding. |
| Re-ingest skip-check | < 10 s | Zero embedding calls for unchanged corpus. |
| 40-case eval | < 4 min | At `bfsi_eval_concurrency=5`; dominated by chat-model latency. |
| `docendo doctor --no-embedding` | < 3 s | Offline. |

## How to re-run

```bash
BFSI_RUN_PERF=1 pytest tests/perf -v
```

The benchmarks write a JSON report to `reports/perf.json` for trend
tracking:

```bash
cat reports/perf.json
```

Benchmarks are skipped by default so the default CI lane stays under
3 minutes.

## Why these budgets

- The SQLite store is the dominant local cost (read/write/log). Local
  ingest is fast; the bottleneck is always the embedding API.
- `hybrid_search` runs FTS5 + vector_full_scan + a Python RRF merge. The
  100 ms p95 budget covers up to ~50k chunks per corpus on warm cache.
- The eval budget assumes a hosted chat model at typical MiniMax latencies.
  Local evaluation against a local LLM would be much faster.

## Regression guard

When `BFSI_RUN_PERF=1` is set, a >25% regression against the previous
benchmark report (`reports/perf.json` from the previous run) fails CI.
To reset the baseline, delete `reports/perf.json`.
