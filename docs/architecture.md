# Architecture

## Diagram

```
RBI PDFs ── pypdf/vision-extract ── gigatoken chunk ── LiteLLM embed (Qwen3)
                                          │
                                          ▼
                       SQLite + FTS5 + sqlite-vector
                       (data/processed/rbi-circulars.sqlite3)
                                          │
                                          ▼
                  Pydantic AI Agent (MiniMax-M3) + four direct tools
                                          │
                                          ▼
                              Structured RBIAnswer
                                          │
                                          ▼
                            Streamlit A/B Chat UI
```

## Components

| Layer | Responsibility |
|---|---|
| `docendo.ingestion.rbi_scraper` | Discovers RBI PDFs and downloads them to `data/raw/`. |
| `docendo.ingestion.pdf` | Extracts text via `pypdf`; falls back to MiniMax vision for scanned pages. |
| `docendo.retrieval.tokenizer` | Gigatoken wrapper. Chunks by token count (default 384, overlap 64). |
| `docendo.retrieval.embeddings` | LiteLLM embedding client. Batched, retried, in-memory LRU cache. |
| `docendo.retrieval.sqlite_store` | SQLite + FTS5 + sqlite-vector backend. Hybrid search via RRF. |
| `docendo.retrieval.factory` | Process-wide singleton retriever, cached on `(path, settings)`. |
| `docendo.retrieval.tools` | Four Pydantic AI tool functions: `hybrid_search`, `get_circular`, `list_recent`, `compare_circulars`. |
| `docendo.agent` | Pydantic AI agent factory. Tools attached when `grounded=True`. |
| `docendo.eval` | Atomic-claim LLM-as-judge evaluation pipeline. |
| `docendo.ui.streamlit_app` | A/B chat demo. |
| `docendo.cli.doctor` | Local diagnostics. |

## Tool surface

| Tool | Inputs | Output | Backend calls |
|---|---|---|---|
| `hybrid_search` | `query: str (1-512)`, `limit: int (1-20)` | `SearchResponse` (ranked hits) | FTS5 `bm25` + `vector_full_scan` + RRF fusion in Python |
| `get_circular` | `id: str` (regex-validated) | `CircularResponse` (chunks in order) | `chunks` table filtered by `circular_id`, ordered by `chunk_index` |
| `list_recent` | `since: YYYY-MM-DD`, `limit: int (1-20)` | `list[RecentItem]` (first chunks) | Partial index `idx_chunks_first_recent` |
| `compare_circulars` | `id_a, id_b: str` | `CompareResponse` (two `CircularResponse`s) | Two `get_circular` calls |

## Data model

`chunks` table:

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | rowid |
| `circular_id` | TEXT | Unique with `chunk_index` |
| `title` | TEXT | — |
| `text` | TEXT | chunk text (≤ `bfsi_max_chars_per_result`) |
| `issue_date` | TEXT (nullable) | ISO 8601 |
| `topic` | TEXT (nullable) | — |
| `source_url` | TEXT | rbi.org.in URL |
| `page_start`, `page_end` | INTEGER | best-effort provenance |
| `chunk_index`, `chunk_count` | INTEGER | 0-indexed within circular |
| `extraction_method` | TEXT | `text` or `mixed` (vision pages) |
| `content_hash` | TEXT | SHA-256 of PDF bytes; powers re-ingest skip |
| `embedding` | BLOB | sqlite-vector `FLOAT32` of `bfsi_embedding_dims` |

`chunks_fts` (FTS5 virtual table): mirrors `chunks.title` and `chunks.text`.
Synchronized via `chunks_ai`, `chunks_ad`, `chunks_au` triggers. Tokenized by
FTS5's built-in `unicode61` tokenizer with diacritics removed.

`chunks_meta`: `key`/`value` rows storing `schema_version`,
`embedding_model`, `embedding_dims`, `tokenizer_model`.

## Concurrency model

- One `SQLiteStore` per `(path, settings)` per process. Constructed via
  `functools.lru_cache` in `factory.get_retriever`.
- WAL mode allows concurrent readers; one writer at a time via a
  per-path `threading.Lock`.
- `PRAGMA busy_timeout=5000` keeps well-behaved writers from failing.
- Embedding calls happen on the asyncio event loop (LiteLLM is async).
  SQLite writes are offloaded via `asyncio.to_thread` so they never
  stall the loop.

## Failure modes

- **Embedding endpoint down**: `EmbeddingProviderError` propagates out of
  the tool / pipeline with the model id and base URL in the message.
- **Tokenizer fails to load**: `ConfigurationError` at the first call
  to `chunk_text`. Surface this early via `docendo doctor`.
- **SQLite corruption**: partial FTS5 entries can be repaired via
  `INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild');`.
- **Re-ingestion of an unchanged PDF**: skipped at the `content_hash`
  short-circuit, with zero embedding calls and zero extraction.

## What is NOT here

- No Elasticsearch, Kibana, Agent Builder, ELSER, or ES|QL. Those code
  paths were removed in `v0.2.0`; see `CHANGELOG.md`.
- No `MCP` Pydantic AI capability. The agent uses direct tool functions.
- No public HTTPS host for the corpus. The SQLite store is local.
