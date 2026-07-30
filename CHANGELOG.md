# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0a1] - 2026-07-31

### Added
- **Package renamed:** `bfsi-rbi` -> `docendo` (PyPI-verified available).
- **Single-word naming** across the entire public surface:
  - `make_agent` -> `agent`; `run_eval` -> `run`; `run_ingestion` -> `run`; etc.
  - All public classes: `SearchHit` -> `Hit`, `SearchResponse` -> `Results`,
    `CircularResponse` -> `Document`, `RecentItem` -> `Listing`,
    `CompareResponse` -> `PairResult`, `HybridSearchInput` -> `Query`,
    `GetCircularInput` -> `Lookup`, `ListRecentInput` -> `Recent`,
    `CompareInput` -> `Pair`, `Citation` -> `Cite`, `RBIAnswer` -> `Answer`,
    `ExtractedPage` -> `Page`, `ExtractedDocument` -> `Record`,
    `HallucinationResult` -> `Verdict`, `AtomicClaim` -> `Claim`,
    `AtomicClaimHallucination` -> `Judge`, `EvalCase` -> `Case`,
    `CaseResult` -> `Outcome`, `EvalReport` -> `Report`,
    `SQLiteStore` -> `Store`, etc.
  - All tool functions: `hybrid_search` -> `search`, `get_circular` -> `fetch`,
    `list_recent` -> `recent`, `compare_circulars` -> `compare`.
- **No `_` prefix anywhere** in user-visible code; privacy signaled by
  module name (e.g., `retrieval/_internal.py`).
- **ChunkRecord Pydantic model** replaces `dict[str, Any]` round-trips;
  typos at the boundary now raise `ValidationError`.
- **page_estimate_start / page_estimate_end** fields in `ChunkRecord`
  (document-level estimates; not per-chunk page provenance).
- **`Settings.rrf_k`** configurable; the RRF fusion denominator.
- **`KNOWN_GAPS.md`** at repo root lists deferred items (MCP server, Agent
  Builder attach, Elastic backend, public HTTPS host, update-corpus, etc.).
- **`bfsi-rbi doctor` -> `docendo checkup`** with `--no-embedding` and
  `--no-tokenizer` flags for offline CI.
- **`docendo cases`** replaces `dataset-info`.

### Changed
- **Env vars:** dropped `BFSI_*`, `MINIMAX_*`, `RBI_*`, `ELASTIC_*` prefixes;
  single-word uppercase: `CHAT_URL`, `VECTOR_BASE`, `TOKENIZER_MODEL`,
  `STORE_PATH`, `CHUNK_SIZE`, etc.
- **`Settings` fields** renamed to match (chat_url, vector_model, store_path,
  chunk_size, etc.).
- **`Settings.chat` / `Settings.vector_id` properties** replace
  `litellm_model` / `litellm_embedding_model`.
- **Module renames:** `cli/doctor.py` -> `cli/checkup.py`,
  `ingestion/pdf.py` -> `ingestion/reader.py`,
  `ingestion/pipeline.py` -> `ingestion/ingest.py`,
  `ingestion/rbi_scraper.py` -> `ingestion/scraper.py`,
  `retrieval/sqlite_store.py` -> `retrieval/store.py`,
  `retrieval/tokenizer.py` -> `retrieval/chunker.py`,
  `retrieval/embeddings.py` -> `retrieval/embedder.py`,
  `retrieval/factory.py` -> `retrieval/_internal.py`,
  `eval/hallucination.py` -> `eval/judge.py`,
  `eval/runner.py` -> `eval/driver.py`,
  `eval/report.py` -> `eval/summarize.py`,
  `eval/dataset.py` -> `eval/cases.py`,
  `ui/streamlit_app.py` -> `ui/app.py`.
- **`embedder.aembed`** raises `EmbeddingProviderError` on empty/partial
  vectors; no silent `[]` returns.
- **`judge.extract`** returns `None` on parse failure; the case is excluded
  from aggregate (zero claims), not biased as `extra`.
- **`judge.score`** typed `-> Verdict` (was `-> Verdict_` shadowing a literal
  type alias).
- **`SQLiteStore`** uses `row_factory = sqlite3.Row`; all row reads go
  through named columns (column-order independence).
- **`agent(settings=...)`** actually honors the `settings` argument; the model
  cache is keyed on `(chat_url, chat_key, chat_model)`.
- **`cli report`** reconstructs `Verdict` from JSONL with proper int coercion
  and full type annotation; preserves `claims`.
- **`README` and all docs** rewritten with the new package name; the four
  brand phrases (`BFSI-RBI`, `bfsi-rbi`, `rbi-circulars`, `MINIMAX_API_KEY`)
  no longer appear in user docs.
- **`Makefile`** target list updated to match the new CLI surface
  (`checkup`, `checkup-fast`, `test-int`, `test-perf`, `cases`).
- **`pyproject.toml`** upper-bounds every runtime dep; `pydantic-ai` is
  now `>=1.0,<2.0`, `pydantic-ai-litellm>=0.2.8`, `pydantic-evals>=1.0`.
- **`sqliteai-vector` runtime dep** with upper bound `<2`.

### Removed
- All Elasticsearch code paths: `src/docendo/es/`,
  `src/docendo/agent_builder/`, `scripts/setup_inference.py`.
- Agent Builder CLI commands: `setup-inference`, `deploy-tools`,
  `deploy-agent`, `smoke-mcp`.
- Pydantic AI `MCP` capability; the agent is grounded via four direct
  Pydantic AI tool functions.
- `logfire` dependency.
- Dead env vars: `ELASTIC_URL`, `ELASTIC_API_KEY`, `ELASTIC_MCP_URL`,
  `BFSI_INDEX_NAME`, `MINIMAX_*`, `BFSI_*`.
- Dead tests: `tests/unit/test_hallucination_smoke.py`,
  `tests/unit/test_pdf_extraction.py`,
  `tests/integration/test_es_roundtrip.py`,
  `tests/integration/test_agent_builder.py`,
  `tests/unit/test_tool_specs.py`.
- Placeholder docs: `docs/known-gaps.md`, `docs/agent-builder-attach.md`,
  `docs/deploy-mcp.md` (replaced by repo-root `KNOWN_GAPS.md`).

### Fixed
- **Judge parse failures** no longer silently bias the hallucination rate.
- **Empty embeddings** raise instead of corrupting sqlite-vector BLOB writes.
- **Page provenance** is now explicitly labelled as document-level estimate
  (no longer misrepresented as per-chunk).
- **`make_agent(settings=...)`** actually uses the supplied settings instead
  of silently dropping the argument.
- **`Store.hybrid_search`** uses named-column access; adding a `SELECT`
  column no longer shifts every row read.

### Security
- No new secrets introduced. The four documented secrets (`CHAT_KEY`,
  `VECTOR_KEY`, `VECTOR_BASE`, future MCP bearer) are the entire surface.
- `eval/report` no longer accepts JSONL `Verdict` rows that include the
  derived `hallucination_rate` / `grounding_score` as constructor args;
  filtered at deserialization.

## [0.2.0] - 2026-07-31

### Added
- Local-first SQLite retrieval backend (sqliteai-vector + FTS5 + gigatoken).
- Four direct Pydantic AI tool functions: `hybrid_search`, `get_circular`,
  `list_recent`, `compare_circulars`.
- `bfsi-rbi doctor` CLI for local diagnostics (SQLite opens, vector extension,
  embedding endpoint, tokenizer load, tokenizer/embedding match).
- Process-wide singletons for the retriever store and the LiteLLM model.
- Content-hash-based re-ingestion skip (zero embedding calls on unchanged PDFs).
- Token-based chunking via gigatoken (default 384 tokens, 64 overlap).
- `LICENSES/sqliteai-vector.md` and `NOTICE` documenting the modified Elastic
  License 2.0 of the SQLite-Vector extension.

### Removed
- All Elasticsearch code paths: `src/bfsi_rbi/es/`,
  `src/bfsi_rbi/agent_builder/`, `scripts/setup_inference.py`.
- Agent Builder CLI commands: `setup-inference`, `deploy-tools`,
  `deploy-agent`, `smoke-mcp`.
- Pydantic AI `MCP` capability; the agent is grounded via four direct
  Pydantic AI tool functions.

## [0.1.0] - 2026-07-29

### Added
- Initial scaffold: RBI scraper, PDF extraction (pypdf + vision fallback),
  Elasticsearch ingestion, Elastic Agent Builder deploy + MCP smoke,
  Pydantic AI agent with MCP grounding, atomic-claim LLM-as-judge
  evaluation, Streamlit A/B demo.
