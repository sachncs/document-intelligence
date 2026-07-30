# docendo

> A grounded RAG agent for BFSI (Banking, Financial Services, Insurance) document intelligence.
> Built on Pydantic AI + LiteLLM (MiniMax-M3) + local SQLite + Qwen3-Embedding-8B.

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

## What it does

Answer questions about RBI (Reserve Bank of India) circulars, master directions, and policy documents with:

- **Hybrid search** (BM25 + cosine-similarity vector) over a local SQLite database.
- **Citation-grounded answers** — every claim is backed by a cited circular.
- **Measured hallucination rate** — side-by-side comparison against an ungrounded LLM baseline using atomic-claim LLM-as-judge.

## Architecture

```
RBI PDFs → pypdf / vision → gigatoken chunk → LiteLLM embed (Qwen3)
                                            ↓
                          SQLite + FTS5 + sqlite-vector
                          (data/processed/rbi-circulars.sqlite3)
                                            ↓
                  Pydantic AI Agent (MiniMax-M3) + four direct tools
                                            ↓
                              Structured RBIAnswer
                                            ↓
                            Streamlit A/B Chat UI
```

The four retrieval tools are direct Python functions registered with the
Pydantic AI agent:

| Tool | Purpose |
|---|---|
| `hybrid_search(query, limit)` | Lexical + vector hybrid search, RRF-fused. |
| `get_circular(id)` | Fetch all chunks of a single circular. |
| `list_recent(since, limit)` | List first-chunk rows since an ISO date. |
| `compare_circulars(id_a, id_b)` | Side-by-side comparison. |

## Quickstart

```bash
pip install -e .
cp .env.example .env
# Edit .env: MINIMAX_API_KEY + BFSI_EMBEDDING_* (OpenAI-compatible Qwen endpoint).
docendo doctor
docendo fetch
docendo ingest
docendo eval --limit 5
docendo report
docendo demo
```

## Evaluation

40 gold Q/A pairs measured against an ungrounded baseline:

| Backend | Ungrounded hallu. | Grounded hallu. | Reduction |
|---|---|---|---|
| **SQLite (local-only)** | _TBD_ | _TBD_ | _TBD_ |

_Numbers populated after the first `docendo eval` run. See
`reports/eval_report.md`._

## Documentation

Full docs: `mkdocs serve` → http://127.0.0.1:8000

| Document | What's in it |
|---|---|
| `docs/quickstart.md` | Five-step setup. |
| `docs/installation.md` | Wheels, env vars, platform matrix. |
| `docs/architecture.md` | Diagram, components, data model, concurrency. |
| `docs/evaluation.md` | Pipeline, judge, report contents. |
| `docs/security.md` | Secrets, network egress, FTS5 hardening, CVE. |
| `docs/known-gaps.md` | What's deferred. |
| `docs/performance.md` | Performance budgets and how to re-run. |

## Development

```bash
pytest tests/unit                                              # unit tests
pytest tests/integration -m "not perf"                         # offline integration
docendo doctor --no-embedding --no-tokenizer                  # offline diagnostics
ruff check src tests                                           # lint
ruff format src tests                                          # format
mypy src/docendo                                              # type check
```

## License

Apache-2.0 — see `LICENSE`. The SQLite-Vector extension is distributed under
the modified Elastic License 2.0; see `LICENSES/sqliteai-vector.md` and
`NOTICE` for the conditions.
