# bfsi-rbi

> A grounded RAG agent for BFSI (Banking, Financial Services, Insurance) document intelligence.
> Built on Pydantic AI + Elastic Agent Builder + MiniMax-M3 (LiteLLM).

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

## What it does

Answer questions about RBI (Reserve Bank of India) circulars, master directions, and policy documents with:

- **Hybrid search** (BM25 + ELSER semantic) via Elastic Agent Builder
- **Citation-grounded answers** — every claim is backed by a cited circular
- **Measured hallucination rate** — side-by-side comparison against an ungrounded LLM baseline using atomic-claim LLM-as-judge

## Architecture

```
RBI PDFs ── vision-extract ──► Elasticsearch (semantic_text + BM25)
                                    │
                                    ▼
                          Elastic Agent Builder
                          (ES|QL + MCP tools)
                                    │
                                    ▼
MiniMax-M3 ──► Pydantic AI Agent ──► Structured RBIAnswer
                                    │
                                    ▼
                          Streamlit A/B Chat UI
```

## Quickstart

```bash
# Install
pip install -e ".[dev]"

# Configure
cp .env.example .env
# Edit .env with your MINIMAX_* and ELASTIC_* credentials

# Run the full pipeline
bfsi-rbi fetch
bfsi-rbi ingest
bfsi-rbi setup-inference
bfsi-rbi deploy-tools
bfsi-rbi deploy-agent
bfsi-rbi smoke-mcp
bfsi-rbi eval
bfsi-rbi report
bfsi-rbi demo
```

## Evaluation

40 gold Q/A pairs measured against an ungrounded baseline:

| Metric | Ungrounded | Grounded | Reduction |
|---|---|---|---|
| Hallucination rate | _TBD_ | _TBD_ | _TBD_ |
| Citation accuracy | n/a | _TBD_ | n/a |
| Refusal correctness | _TBD_ | _TBD_ | _TBD_ |

_Numbers populated after first `bfsi-rbi eval` run. See `reports/eval_report.md`._

## Development

```bash
pytest tests/unit          # unit tests (no network)
ruff check src tests       # lint
ruff format src tests      # format
mypy src/bfsi_rbi          # type check
pre-commit run --all-files # all checks
```

## Documentation

Full docs: `mkdocs serve` → http://127.0.0.1:8000

## License

Apache-2.0 — see [LICENSE](LICENSE).
