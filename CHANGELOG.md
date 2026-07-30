# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-07-31

### Added
- Local-first SQLite retrieval backend (sqliteai-vector + FTS5 + gigatoken).
- Four direct Pydantic AI tool functions: `hybrid_search`, `get_circular`,
  `list_recent`, `compare_circulars`.
- `docendo doctor` CLI for local diagnostics (SQLite opens, vector extension,
  embedding endpoint, tokenizer load, tokenizer/embedding match).
- Process-wide singletons for the retriever store and the LiteLLM model.
- Content-hash-based re-ingestion skip (zero embedding calls on unchanged PDFs).
- Token-based chunking via gigatoken (default 384 tokens, 64 overlap).
- `LICENSES/sqliteai-vector.md` and `NOTICE` documenting the modified Elastic
  License 2.0 of the SQLite-Vector extension.

### Changed
- `Settings` schema rewritten around SQLite path, embedding endpoint, tokenizer
  id, and chunk token counts. Tokenizer id must match embedding id unless
  `BFSI_ALLOW_TOKENIZER_MISMATCH=1`.
- Default chunk sizes are now tokens, not words.
- Ingestion pipeline emits a per-PDF content_hash before extracting; re-running
  the pipeline skips unchanged PDFs.

### Removed
- All Elasticsearch code paths: `src/docendo/es/`, `src/docendo/agent_builder/`,
  `scripts/setup_inference.py`.
- Agent Builder CLI commands: `setup-inference`, `deploy-tools`, `deploy-agent`,
  `smoke-mcp`.
- Pydantic AI `MCP` capability; the agent is grounded via four direct Pydantic
  AI tool functions.
- `tests/integration/test_es_roundtrip.py`, `tests/integration/test_agent_builder.py`,
  `tests/unit/test_tool_specs.py`.

### Security
- Bearer token / Kibana API key handling for the deleted Elastic backend is
  gone; new tokens must be supplied via the embedding env vars.

## [0.1.0] - 2026-07-29

### Added
- Initial scaffold: RBI scraper, PDF extraction (pypdf + vision fallback),
  Elasticsearch ingestion, Elastic Agent Builder deploy + MCP smoke, Pydantic
  AI agent with MCP grounding, atomic-claim LLM-as-judge evaluation, Streamlit
  A/B demo.
