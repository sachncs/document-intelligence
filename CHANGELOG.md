# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-07-29

### Added
- Hybrid search (BM25 + ELSER semantic) via Elastic Agent Builder MCP tools
- Four Agent Builder tools: `rbi.hybrid_search`, `rbi.get_circular`, `rbi.list_recent`, `rbi.compare_circulars`
- Pydantic AI agent factory with structured `RBIAnswer` output (forced citations)
- LiteLLM-based MiniMax-M3 integration (text + vision)
- PDF extraction with vision-API fallback for scanned RBI documents
- 40-question gold evaluation dataset (12 factual, 10 procedural, 8 cross-circular, 6 date-bounded, 4 trap)
- Atomic-claim hallucination evaluator (custom `pydantic-evals` evaluator)
- Side-by-side Streamlit A/B chat UI (grounded vs ungrounded)
- Typer CLI: `bfsi-rbi {fetch, ingest, setup-inference, deploy-tools, deploy-agent, smoke-mcp, eval, report, demo}`
- End-to-end pipeline: fetch → ingest → deploy → eval → report → demo
- MkDocs documentation site
- GitHub Actions CI (ruff + mypy + pytest)
- Unit + integration test suite
- `pre-commit` configuration
- Apache-2.0 license
