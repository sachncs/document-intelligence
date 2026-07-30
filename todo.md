# docendo 0.3.0a1 — Atomic TODO (52 points, no `_` prefix)

> **Naming rule.** Every public symbol is a single word with no underscores. Private symbols are also single words; their privacy is communicated by the module that contains them (e.g., `_internal` modules), never by a leading `_`. If a name needs an underscore to make sense, it belongs in a different module.
>
> **Lock-ins from review.** Package = `docendo`. Repo URL = `https://github.com/sachin/docendo`. Settings property = `vector_id` (not `vector`). Page provenance = `page_estimate_start` / `page_estimate_end` (kept, not dropped). No Elastic, no MCP, no Agent Builder. Alpha `0.3.0a1` with breaking API changes.
>
> Each numbered item carries one verification test. An item is "done" only when that test is green.

---

## Phase 0 — Pre-flight (5 pts)

### 0.1 Package rename — 1 pt

- [ ] **`pyproject.toml`**: `name = "docendo"`, `version = "0.3.0a1"`, `[project.scripts] docendo = "docendo.cli.main:app"`, `[tool.hatch.build.targets.wheel] packages = ["src/docendo"]`, `[project.urls] Homepage/Documentation/Repository/Issues = https://github.com/sachin/docendo/...`
- [ ] **Create `src/docendo/`** alongside; `git rm` the entire `src/bfsi_rbi/` directory
- [ ] **Update `.github/workflows/ci.yml`** env vars and command paths to `docendo`
- [ ] **Update `Makefile`** default targets to invoke `docendo`
- [ ] **No backward-compat shim** (alpha release; clean break)

**Test:** `tests/unit/test_install.py::test_module_name_matches_pyproject` — `import docendo` succeeds.

### 0.2 Unify `__version__` — 1 pt

- [ ] **`git rm src/docendo/version.py`** (if it exists after rename)
- [ ] **`src/docendo/__init__.py`** reads via `importlib.metadata.version("docendo")` with a hard fallback to `"0.3.0a1"`

**Test:** `test_install.py::test_version_matches_pyproject` — `docendo.__version__ == importlib.metadata.version("docendo")`.

### 0.3 Replace `logfire` with stdlib logging — 1 pt

- [ ] **Remove `logfire>=0.50.0`** from `pyproject.toml:49`
- [ ] **Remove `logfire`** from `pyproject.toml:120` mypy override
- [ ] **`src/docendo/logging.py`** uses `logging` stdlib only; remove all `logfire` references
- [ ] **No file references `logfire`** in `src/`, `tests/`, `docs/`

**Test:** `test_install.py::test_no_logfire_at_import_time` — `import docendo` does not pull `logfire`.

### 0.4 Drop dead env vars and fields — 1 pt

- [ ] **`.env` and `.env.example`** rewritten with only active keys (per §1.5)
- [ ] **DELETE** `ELASTIC_URL`, `ELASTIC_API_KEY`, `ELASTIC_MCP_URL` (never read)
- [ ] **DELETE** `BFSI_INDEX_NAME` field from `Settings`
- [ ] **DELETE** `tests/unit/test_hallucination_smoke.py` (15 lines, no value)

**Test:** `tests/unit/test_config.py::test_no_dead_env_vars_in_example` — parses `.env.example`, asserts every documented key has a `Settings` field.

### 0.5 Pin all runtime deps with upper bounds — 1 pt

- [ ] **Add `<N` upper bound** to every runtime dep: `sqliteai-vector>=1.0.0,<2`, `gigatoken>=0.10,<1.0`, `pydantic-ai>=0.3.0,<1.0`, `pydantic-settings>=2.0.0,<3.0`, `litellm>=1.50.0,<2.0`, `streamlit>=1.35.0,<2.0`, `typer>=0.12.0,<1.0`, `pypdf>=4.0.0,<6.0`, `pypdfium2>=4.0.0,<5.0`, `httpx>=0.27.0,<1.0`, `pydantic>=2.7.0,<3.0`

**Test:** `test_install.py::test_pinned_upper_bounds` — walks `pyproject.toml`, asserts every runtime dep has `<N`.

---

## Phase 1 — Single-word rename, no `_` prefix (14 pts)

### 1.1 Module file renames — 2 pts

- [ ] `src/docendo/cli/doctor.py` → `src/docendo/cli/checkup.py`; `run_doctor` → `run`
- [ ] `src/docendo/ingestion/pdf.py` → `src/docendo/ingestion/reader.py`; `extract_pdf` → `read`
- [ ] `src/docendo/ingestion/pipeline.py` → `src/docendo/ingestion/ingest.py` (avoids 4-syllable `orchestrator` and clash with `eval/driver`)
- [ ] `src/docendo/ingestion/rbi_scraper.py` → `src/docendo/ingestion/scraper.py`; `discover_and_download` → `discover`, `scrape_index_pages` → `scrape`, `download_pdf` → `download`
- [ ] `src/docendo/retrieval/sqlite_store.py` → `src/docendo/retrieval/store.py`; class `SQLiteStore` → `Store`
- [ ] `src/docendo/retrieval/factory.py` → `src/docendo/retrieval/_internal.py` (underscore in module name = privacy signal; rename `_cached_store` → `cached_store`)
- [ ] `src/docendo/retrieval/tokenizer.py` → `src/docendo/retrieval/chunker.py`; `chunk_text` → `chunk`
- [ ] `src/docendo/retrieval/embeddings.py` → `src/docendo/retrieval/embedder.py`; `async_embed_texts` → `aembed`
- [ ] `src/docendo/eval/hallucination.py` → `src/docendo/eval/judge.py`; `evaluate_answer` → `score`, `aevaluate_answer` → `ascore`, `_extract_claims` → `extract`
- [ ] `src/docendo/eval/runner.py` → `src/docendo/eval/driver.py`; `run_eval` → `run`, `_run_with_concurrency` → `run_bounded`
- [ ] `src/docendo/eval/report.py` → `src/docendo/eval/summarize.py`; `generate_report` → `render`, `write_jsonl` → `dump`, fold `_result_to_dict` into `Outcome.to_dict()` (method)
- [ ] `src/docendo/eval/dataset.py` → `src/docendo/eval/cases.py`; `load_dataset` → `load`, `save_dataset` → `save`
- [ ] `src/docendo/ui/streamlit_app.py` → `src/docendo/ui/app.py`; `_render_answer_col` → `render`, `_run_agent` → `ask`, `_judge` → `grade`, `_load_eval_questions` → `load_questions`, `_cached_agents` → `build_agents`
- [ ] **Create `src/docendo/retrieval/_internal/`** package: `lex`, `vec`, `hash`, `key`, `get`, `put`, `build_record`, `parse_blob` — single-word, no underscore

**Test:** `tests/unit/test_module_paths.py` — walks `src/docendo/**/*.py`, asserts every filename is single word (or `__init__.py`, or starts with `_`).

### 1.2 Public class renames (single word) — 2 pts

- [ ] `HybridSearchInput` → `Query`, `GetCircularInput` → `Lookup`, `ListRecentInput` → `Recent`, `CompareInput` → `Pair`
- [ ] `SearchHit` → `Hit`, `SearchResponse` → `Results`, `CircularResponse` → `Document`, `RecentItem` → `Listing`, `CompareResponse` → `PairResult`
- [ ] `Citation` → `Cite`, `RBIAnswer` → `Answer`
- [ ] `ExtractedPage` → `Page`, `ExtractedDocument` → `Record`
- [ ] `DiscoveredDocument` → `Found`, `DiscoveredMasterDirection` → `Direction`
- [ ] `IngestionReport` → `Report` (in ingest), `EvalReport` → `Report` (in summarize) — namespace by import path
- [ ] `HallucinationResult` → `Verdict`, `AtomicClaim` → `Claim`, `AtomicClaimHallucination` → `Judge`
- [ ] `EvalCase` → `Case`, `CaseResult` → `Outcome`
- [ ] `BFSIRBIError` → `Error`

**Test:** `tests/unit/test_public_api.py::test_single_word_public_classes` — `dir(docendo.X)` for each module, every class name has no underscore.

### 1.3 Public + file-private function/method renames — 3 pts

- [ ] `make_agent` → `agent` (factory); `build_litellm_model` → `build` (file-private); `GRCIT_SYSTEM_PROMPT` → `SYSTEM_PROMPT`
- [ ] `extract_text_via_vision` → `read_page`; `render_page_to_png` → `render_page`; `_parse_issue_date` → `parse_date`
- [ ] `cosine_similarity` → `cosine`; `_lexical_search` → `lex`; `_vector_search` → `vec` (in `Store` and `_internal`)
- [ ] `_hash` → `hash`; `_cache_key` → `key`; `_cache_get` → `get`; `_cache_set` → `put` (in `_internal`)
- [ ] `_cached_litellm_model` → `model`; `_tool_functions` → `tools` (file-private in `agent.py`)
- [ ] `_validate_chunk_overlap` → `validate_chunk_overlap` (model validator = public API)
- [ ] `_callback`, `_root` → `configure`, `root` (file-private in `cli/main.py`)
- [ ] `_content_hash`, `_build_chunks` → `hash_pdf`, `build_records` (file-private in `ingest.py`)
- [ ] `_http_get`, `_safe_circular_id`, `_parse_pdf_links` → `http_get`, `slugify`, `parse_links` (file-private in `scraper.py`)
- [ ] `_sha256`, `_split_page_text` → `sha256_file`, `split_page` (file-private in `reader.py`)
- [ ] `_to_text`, `_to_citations` → `Outcome.text()` / `Outcome.citations()` (methods, not free functions)
- [ ] `_check_sqlite_opens`, `_check_vector_extension`, `_check_tokenizer`, `_check_minimax`, `_check_tokenizer_match`, `_check_paths`, `_check_embeddings`, `_check_tokenizer_load` → `sqlite`, `vector`, `tokenizer`, `chat`, `match`, `paths`, `embed`, `tokenizer_load` (file-private in `checkup.py`)
- [ ] `run_doctor` → `run`

**Test:** `tests/unit/test_no_underscore_prefix.py` — `grep -rE "^def _\w+|^    def _\w+|^        def _\w+" src/docendo/` returns zero hits.

### 1.4 Tool function renames (single-word public tools) — 1 pt

- [ ] `hybrid_search` → `search`; `get_circular` → `fetch`; `list_recent` → `recent`; `compare_circulars` → `compare`
- [ ] **Update `agent.py`** `tools` list and `SYSTEM_PROMPT` references
- [ ] **Update `tests/unit/test_agent_factory.py::TestToolFunctions.test_tool_function_names`**

**Test:** `from docendo.retrieval.tools import search, fetch, recent, compare` succeeds.

### 1.5 Env var renames (single word, all uppercase) — 1 pt

- [ ] `MINIMAX_BASE_URL` → `CHAT_URL`; `MINIMAX_API_KEY` → `CHAT_KEY`; `MINIMAX_MODEL` → `CHAT_MODEL`
- [ ] `BFSI_SQLITE_PATH` → `STORE_PATH`
- [ ] `BFSI_EMBEDDING_PROVIDER` → `VECTOR_PROVIDER`; `BFSI_EMBEDDING_MODEL` → `VECTOR_MODEL`; `BFSI_EMBEDDING_DIMS` → `VECTOR_DIMS`; `BFSI_EMBEDDING_API_KEY` → `VECTOR_KEY`; `BFSI_EMBEDDING_API_BASE` → `VECTOR_BASE`; `BFSI_EMBEDDING_BATCH_SIZE` → `VECTOR_BATCH`
- [ ] `BFSI_TOKENIZER_MODEL` → `TOKENIZER_MODEL`; `BFSI_ALLOW_TOKENIZER_MISMATCH` → `TOKENIZER_ALLOW_MISMATCH`
- [ ] `BFSI_CHUNK_SIZE_TOKENS` → `CHUNK_SIZE`; `BFSI_CHUNK_OVERLAP_TOKENS` → `CHUNK_OVERLAP`; `BFSI_MAX_CHARS_PER_RESULT` → `CHUNK_MAX_CHARS`
- [ ] `BFSI_EVAL_CONCURRENCY` → `EVAL_CONCURRENCY`; `BFSI_EVAL_LIMIT` → `EVAL_LIMIT`
- [ ] `BFSI_LOG_LEVEL` → `LOG_LEVEL`; `BFSI_HTTP_TIMEOUT` → `HTTP_TIMEOUT`; `BFSI_LLM_TIMEOUT` → `CHAT_TIMEOUT`
- [ ] `RBI_FETCH_MAX_DOCS` → `FETCH_MAX_DOCS`
- [ ] **DELETE** `BFSI_INDEX_NAME`, `ELASTIC_*`
- [ ] **KEEP** `BFSI_RUN_PERF`, `BFSI_RUN_INTEGRATION` (CI hooks)

**Test:** `tests/unit/test_config.py::test_env_aliases_map_old_to_new` — every old name is rejected by `Settings`.

### 1.6 `Settings` field renames — 1 pt

- [ ] `minimax_base_url` → `chat_url`; `minimax_api_key` → `chat_key`; `minimax_model` → `chat_model`
- [ ] `bfsi_sqlite_path` → `store_path`
- [ ] `bfsi_embedding_provider` → `vector_provider`; `bfsi_embedding_model` → `vector_model`; `bfsi_embedding_dims` → `vector_dims`; `bfsi_embedding_api_key` → `vector_key`; `bfsi_embedding_api_base` → `vector_base`; `bfsi_embedding_batch_size` → `vector_batch`
- [ ] `bfsi_tokenizer_model` → `tokenizer_model`; `bfsi_allow_tokenizer_mismatch` → `tokenizer_allow_mismatch`
- [ ] `bfsi_chunk_size_tokens` → `chunk_size`; `bfsi_chunk_overlap_tokens` → `chunk_overlap`; `bfsi_max_chars_per_result` → `chunk_max_chars`
- [ ] `bfsi_eval_concurrency` → `eval_concurrency`; `bfsi_eval_limit` → `eval_limit`
- [ ] `bfsi_log_level` → `log_level`; `bfsi_http_timeout` → `http_timeout`; `bfsi_llm_timeout` → `chat_timeout`
- [ ] `rbi_fetch_max_docs` → `fetch_max_docs`
- [ ] **DELETE** `bfsi_index_name`
- [ ] **ADD** `rrf_k: int = Field(default=60, ge=1, le=1000)` (per §2.9)

**Test:** `tests/unit/test_config.py::test_settings_field_count` — asserts documented field count.

### 1.7 `Settings.chat` / `Settings.vector_id` properties — 1 pt

- [ ] `Settings.litellm_model` → `Settings.chat` (returns `f"{provider}/{chat_model}"`)
- [ ] `Settings.litellm_embedding_model` → `Settings.vector_id` (unambiguous: it's a model id, not storage)
- [ ] **Update all call sites** in `agent.py`, `embedder.py`, `ingest.py`, `checkup.py`

**Test:** `tests/unit/test_config.py::test_chat_and_vector_id_properties`.

### 1.8 CLI subcommand renames — 1 pt

- [ ] `bfsi-rbi fetch` → `docendo fetch`; `ingest` → `docendo ingest`; `eval` → `docendo eval`; `report` → `docendo report`; `demo` → `docendo demo`; `doctor` → `docendo checkup`; `dataset-info` → `docendo cases`
- [ ] **Update Makefile** targets to match

**Test:** `tests/integration/test_cli_smoke.py::test_subcommand_names` — `docendo --help` lists every subcommand.

### 1.9 CLI flag renames — 1 pt

- [ ] **DROP** `--raw`; use `--source-dir`
- [ ] **DROP** `--chunk-size-tokens`, `--chunk-overlap-tokens`; use `--chunk-size`, `--chunk-overlap`
- [ ] **KEEP** `--max`, `--limit`, `--concurrency`, `--port`, `--host`, `--no-embedding`, `--no-tokenizer`, `--out`

**Test:** `tests/integration/test_cli_smoke.py::test_flags_match_documented_set`.

### 1.10 `agent(settings=...)` semantic fix — 1 pt

- [ ] **`agent.py`** honors the `settings` argument; `_cached_model` keyed on `(chat_model, chat_key, chat_base)`
- [ ] **`reset_settings_cache`** in `config.py` also clears the model cache

**Test:** `tests/unit/test_agent_factory.py::test_settings_change_invalidates_model` — two `Settings` with different `chat_key` yield two distinct models.

### 1.11 `agent()` collision with `pydantic_ai.Agent` — 1 pt

- [ ] In `agent.py`, import as `from pydantic_ai import Agent as PydanticAgent`
- [ ] Internal usages become `PydanticAgent(...)`
- [ ] Public `agent()` factory function unchanged

**Test:** `tests/unit/test_agent_factory.py::test_grounded_has_four_tools` patches `docendo.agent.PydanticAgent`.

### 1.12 `Makefile` cleanup — 1 pt

- [ ] **DELETE** `setup-inference`, `deploy-tools`, `deploy-agent`, `smoke-mcp` targets
- [ ] **UPDATE** `ingest` help text (currently says "Elasticsearch")
- [ ] **ADD** `checkup`, `perf`, `cases` targets

**Test:** `make help` exits 0 and lists only existing targets.

### 1.13 Drop dead `_write_lock` — included in §1.1 (`Store` refactor) — 0 pts

Combined with §1.1 module refactor.

### 1.14 `Settings.make_agent(settings=...)` silent no-op — included in §1.10 — 0 pts

Combined with §1.10.

---

## Phase 2 — Data-flow fixes (8 pts)

### 2.1 Real PDF text extraction test — 1 pt

- [ ] **Add `tests/fixtures/text_only.pdf`** — real one-page PDF with extractable text (build via pypdf in a fixture factory)
- [ ] **`tests/unit/test_reader.py::TestRead.test_reads_text_via_pypdf`** asserts `len(pages) == 1` and `pages[0].text` contains a known phrase
- [ ] **`test_vision_fallback_on_blank_page`** mocks `litellm.completion`, asserts it was called once
- [ ] **DELETE `tests/unit/test_pdf_extraction.py`** (redundant with `test_reader.py`)

**Test:** runs offline; no real LLM call.

### 2.2 Pydantic `ChunkRecord` model — 1 pt

- [ ] **New `src/docendo/retrieval/record.py`** defines `ChunkRecord` with fields: `id`, `circular_id`, `title`, `text`, `issue_date`, `topic`, `source_url`, `page_estimate_start`, `page_estimate_end`, `chunk_index`, `chunk_count`, `extraction_method`, `content_hash`, `embedding`
- [ ] **`Store.upsert_chunks(circular_id, records: list[ChunkRecord])`** (typed signature)
- [ ] **`ingest.py::build_records()`** returns `list[ChunkRecord]`

**Test:** `tests/unit/test_record.py::test_typographic_typo_raises_validation_error`.

### 2.3 Fix `Store.lex` / `Store.vec` column-position fragility — 1 pt

- [ ] **`store.py`** uses `row_factory = sqlite3.Row`
- [ ] **Reads** go through `row["chunk_index"]` not `row[7]`
- [ ] **Same change** for hits construction and `fetch`

**Test:** `tests/unit/test_store.py::test_column_order_independence`.

### 2.4 Page provenance as estimates (override: keep, rename) — 1 pt

- [ ] **`ChunkRecord`** keeps `page_estimate_start` and `page_estimate_end` (override)
- [ ] **Default values** `page_estimate_start=1, page_estimate_end=N` where N is `len(extracted.pages)` for every chunk
- [ ] **`build_records()` docstring**: "These are document-level estimates, not actual chunk→page mappings. RAG citations should not quote page numbers from these fields."
- [ ] **`docs/architecture.md`** updated: "page_estimate_start/end are document-level spans, NOT per-chunk page provenance."

**Test:** `tests/unit/test_record.py::test_page_estimate_fields_present`.

### 2.5 Surface `issue_date IS NULL` circulars — 1 pt

- [ ] **`Store.list_recent(since, limit, include_unknown_date=False)`** — new parameter
- [ ] **`cli/checkup.py::match`** reports count of `NULL` dates
- [ ] **`KNOWN_GAPS.md`** notes this limitation

**Test:** `tests/unit/test_store.py::test_list_recent_includes_null_dates_when_requested`.

### 2.6 Stop swallowing empty embeddings — 1 pt

- [ ] **`embedder.aembed()`** raises `EmbeddingProviderError` if any batch returns an empty vector — no silent `[]`
- [ ] **`parse_blob`** (in `_internal`) raises `StorageError` on empty input
- [ ] **`probe_embedding_dim`** called from `ingest.py::run()` after `ensure_schema()`; refuses on mismatch

**Test:** `tests/integration/test_provider_fallback.py::test_partial_batch_failure_raises`.

### 2.7 Stop silently dropping `claims` in JSONL — 1 pt

- [ ] **`cli/main.py`** no longer filters `claims` from `Verdict` reconstruction
- [ ] **`eval/summarize.py::render`** adds a "Per-case breakdown" section with first 3 claims per case
- [ ] **`Outcome.to_dict()`** keeps `claims` (already does)

**Test:** `tests/integration/test_eval_pipeline.py::test_results_jsonl_round_trip_preserves_claims`.

### 2.8 Typed exceptions everywhere — 1 pt

- [ ] **`ingest.py::_process_one`** catches `EmbeddingProviderError | ScrapingError | StorageError | VisionAPIError | ConfigurationError` only
- [ ] **`embedder.aembed()`** retry loop catches `EmbeddingProviderError` only

**Test:** `tests/unit/test_ingest.py::test_typed_error_propagation`.

---

## Phase 3 — Public surface cleanup (5 pts)

### 3.1 Public root exports — 1 pt

- [ ] **`src/docendo/__init__.py`** re-exports: `agent`, `Answer`, `Cite`, `Case`, `Verdict`, `Report`, `load`, `run`, `vector_id`, `chat`, `Error`, `Store`

**Test:** `tests/unit/test_install.py::test_root_reexports_documented_api`.

### 3.2 Remove dead code — 1 pt

- [ ] **DELETE** `tests/unit/test_hallucination_smoke.py`
- [ ] **DELETE** `tests/unit/test_pdf_extraction.py` (replaced by `test_reader.py`)
- [ ] **DELETE** `_write_lock` (replaced by per-instance lock inside `Store.__init__`)

**Test:** `tests/unit/test_dead_code.py` — greps for known dead symbols, zero hits.

### 3.3 `__init__.py` files are intentional — 1 pt

- [ ] **Every package** has a re-export `__init__.py` with `__all__`
- [ ] **Internal modules** (`reader`, `chunker`, `embedder`, `store`, `driver`, `judge`, `summarize`, `cases`) NOT re-exported from package `__init__.py`

**Test:** `tests/unit/test_public_api.py::test_internal_modules_not_reexported`.

### 3.4 Single source of truth for settings — 1 pt

- [ ] **`Settings`** and **`reset_settings_cache`** only in `docendo.config`
- [ ] **`agent.py`** no longer has its own cache; the cache lives in `docendo.config` and is keyed on `(chat_model, chat_key, chat_base)`

**Test:** `grep -rn "def get_settings" src/docendo` returns exactly one hit.

### 3.5 Docstrings follow one style — 1 pt

- [ ] **Every public function/class** has a docstring starting with a one-line imperative summary
- [ ] **No "this file does X" placeholders**

**Test:** `tests/unit/test_docstrings.py::test_no_trailing_whitespace_or_stale_comments`.

---

## Phase 4 — Tests that verify, not just call (10 pts)

### 4.1 RRF fusion correctness test (real vectors) — 1 pt

- [ ] **`tests/unit/test_store.py::TestHybrid.test_rrf_fusion_order_realistic`**:
  - 5 circulars with hand-crafted embeddings where lexical and vector ranks differ
  - Asserts fused order matches expected RRF order with k=60
  - Asserts changing `Settings.rrf_k` changes the order

**Test:** asserts the algorithm.

### 4.2 Eval judge correctness test (real data) — 1 pt

- [ ] **`tests/unit/test_judge.py::test_score_correct_vs_contradicted_vs_extra`** — 3 hand-crafted (gold, answer) pairs
- [ ] **Mocks LLM** but asserts on aggregate score

**Test:** catches `extra` ↔ `contradicted` flips.

### 4.3 CLI smoke tests — 1 pt

- [ ] **`tests/integration/test_cli_smoke.py`** covers `help`, `checkup --no-embedding`, `cases`, `report` on minimal JSONL, `ingest` on empty dir

**Test:** Typer `CliRunner`, no real network.

### 4.4 Fetch against canned HTML — 1 pt

- [ ] **`tests/fixtures/master_directions_sample.html`** — real RBI-like HTML fragment
- [ ] **Stub `httpx.Client.get`**, assert `discover()` yields 5 `Found` records

**Test:** catches parser regressions.

### 4.5 Concurrency under contention — 1 pt

- [ ] **`tests/integration/test_concurrency.py::test_contended_writer_no_corruption`**:
  - 1 writer, 10 readers, 200 iterations
  - Every `circular_id` has 0 or exactly N chunks

**Test:** catches `SQLITE_BUSY` and torn writes.

### 4.6 Eval round-trip preserves `claims` — 1 pt

- [ ] **`tests/integration/test_eval_pipeline.py::test_jsonl_round_trip_preserves_claims`**

**Test:** catches the `cli/main.py` strip bug.

### 4.7 Tool return-shape validation — 1 pt

- [ ] **`tests/unit/test_tools.py::test_get_circular_not_found_returns_marker`**
- [ ] **Same for `compare_circulars`**

**Test:** catches the dict-returning tools.

### 4.8 Embedding cache correctness — 1 pt

- [ ] **`tests/unit/test_embedder.py::test_cache_returns_same_vector_on_second_call`**
- [ ] **`test_cache_key_includes_dims`**
- [ ] **`test_cache_evicts_at_max_size`**

**Test:** catches `_CACHE` invariant violations.

### 4.9 CLI end-to-end with mocked LLM — 1 pt

- [ ] **`tests/integration/test_cli_e2e.py::test_docendo_eval_smoke_5_cases`**

**Test:** catches regressions in `eval/driver.py`.

### 4.10 Performance benchmarks CI-friendly — 1 pt

- [ ] **`tests/perf/test_benchmarks.py`** already gated
- [ ] **`pyproject.toml` `[tool.pytest] markers`** adds `perf`
- [ ] **`pyproject.toml [tool.pytest] addopts`** excludes `perf` from default discovery: `addopts = ["-ra", "--strict-markers", "--strict-config", "-m", "not perf"]`

**Test:** `pytest tests/` (no env var) skips all perf tests.

---

## Phase 5 — Docs, release, packaging (10 pts)

### 5.1 Rewrite README — 1 pt

- [ ] **Single-word brand** "docendo"
- [ ] **Real example outputs** (no `_TBD_`)
- [ ] **Quickstart** actually works (test in CI per §5.10)

### 5.2 `KNOWN_GAPS.md` at repo root — 1 pt

- [ ] **New file `KNOWN_GAPS.md`** at repo root (not under `docs/`)
- [ ] **DELETE** `docs/known-gaps.md`
- [ ] **Lists**: page provenance is estimate-only, `issue_date IS NULL` circulars filter from `recent`, future MCP/Elastic/Agent Builder are deferred

**Test:** `tests/unit/test_documentation.py::test_known_gaps_at_repo_root`.

### 5.3 `CONTRIBUTING.md` — 1 pt

- [ ] **`pip install -e ".[dev]"`** documented
- [ ] **`pre-commit install`**
- [ ] **`pytest tests/unit`** for fast feedback
- [ ] **`BFSI_RUN_PERF=1 pytest tests/perf -v`** for benchmarks
- [ ] **How to add a new retrieval tool** (the four-tool pattern)
- [ ] **How to add a new eval case** (`eval/cases.yaml` is the dataset)

### 5.4 `CHANGELOG.md` entry for `0.3.0a1` — 1 pt

- [ ] **Document all 52 atomic changes**
- [ ] Mark this release as alpha (breaking API changes)

### 5.5 `pyproject.toml` final pass — 1 pt

- [ ] **`name = "docendo"`**, **`version = "0.3.0a1"`**
- [ ] **`[project.scripts] docendo = "docendo.cli.main:app"`**
- [ ] **All runtime deps pinned with `<N`**
- [ ] **`[project.urls]`** updated to `https://github.com/sachin/docendo/...`
- [ ] **`[tool.pytest] markers`** adds `perf`
- [ ] **`[tool.pytest] addopts`** excludes `perf`

### 5.6 `sdist` build is clean — 1 pt

- [ ] **`python -m build`** produces `dist/docendo-0.3.0a1.tar.gz` and `.whl`
- [ ] **`pip install`** in fresh venv works
- [ ] **`docendo --help`** runs

**Test:** `tests/integration/test_wheel.py::test_wheel_install_and_help`.

### 5.7 `LICENSE` and `NOTICE` cover bundled deps — 1 pt

- [ ] **`LICENSE`** is Apache-2.0
- [ ] **`NOTICE`** lists SQLite-Vector (modified Elastic License 2.0) and gigatoken (MIT)
- [ ] **`LICENSES/sqliteai-vector.md`** and **`LICENSES/gigatoken.md`** in wheel
- [ ] **`[tool.hatch.build.targets.wheel]`** includes `LICENSES/` and `NOTICE`

**Test:** `tests/unit/test_install.py::test_notice_present_and_correct`.

### 5.8 `Makefile` is consistent — 1 pt

- [ ] **DELETE obsolete targets**
- [ ] **ADD** `checkup`, `perf`, `cases` targets

### 5.9 `py.typed` and sdist contents — 1 pt

- [ ] **Confirm `src/docendo/py.typed`** exists
- [ ] **`[tool.hatch.build.targets.sdist]`** excludes `tests/`
- [ ] **Wheel is `py3-none-any`**

### 5.10 README quickstart end-to-end test — 1 pt

- [ ] **`tests/integration/test_readme_quickstart.py::test_quickstart_in_clean_venv`**:
  - Create fresh venv
  - Install the wheel
  - Run `docendo checkup --no-embedding` — exit 0
  - Run `docendo --help` — exit 0

**Test:** catches doc-vs-reality drift.

---

## Tracked debt (not scored)

- [ ] Elastic backend (re-add when MCP returns)
- [ ] Authenticated MCP server
- [ ] Agent Builder attach
- [ ] Public HTTPS host deployment
- [ ] `docendo update-corpus` remote-artifact flow
- [ ] `Dockerfile`/`compose.yaml` for production deployment
- [ ] Native sdist for `sqliteai-vector` if Alpine/musl or Windows ARM become targets
- [ ] `Settings.rrf_k` UI exposure (it's a setting, not in CLI yet)
- [ ] Tool return-shape enforcement via Pydantic (currently tools return dicts)

---

## Scorecard

| Phase | Items | Points |
|---|---|---:|
| 0. Pre-flight | 5 | 5 |
| 1. Single-word rename, no `_` prefix | 14 | 14 |
| 2. Data-flow fixes | 8 | 8 |
| 3. Public surface | 5 | 5 |
| 4. Real tests | 10 | 10 |
| 5. Docs + release | 10 | 10 |
| **Total** | **52** | **52** |
