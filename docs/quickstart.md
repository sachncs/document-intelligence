# Quickstart

## 0. Requirements

- Python 3.11+
- macOS (x86_64 or arm64), glibc Linux (x86_64 or aarch64), or Windows
  x86-64. (Alpine / musl and Windows ARM are not supported — see
  `KNOWN_GAPS.md`.)
- An OpenAI-compatible endpoint serving `Qwen/Qwen3-Embedding-8B`
  (vLLM, Ollama, DashScope, or hosted Qwen inference). Any
  OpenAI-compatible base URL works.
- A MiniMax API key for the chat model.

## 1. Install

```bash
git clone https://github.com/sachin/docendo
cd docendo
pip install -e .
```

For development extras:

```bash
pip install -e ".[dev]"
```

## 2. Configure

```bash
cp .env.example .env
# Edit .env:
#   CHAT_KEY                   (chat model key)
#   CHAT_URL                   (default: https://api.minimax.io/v1)
#   CHAT_MODEL                 (default: MiniMax-M3)
#   VECTOR_KEY                 (your Qwen endpoint key)
#   VECTOR_BASE                (your Qwen endpoint base URL, no trailing /v1)
#   VECTOR_MODEL               (default: Qwen/Qwen3-Embedding-8B)
#   TOKENIZER_MODEL            (default: Qwen/Qwen3-Embedding-8B; must match)
#   VECTOR_DIMS                (default: 4096; verified at startup by checkup)
```

## 3. Sanity check

```bash
docendo checkup
# All checks should pass: paths, chat_creds, tokenizer_match, sqlite_opens,
# vector_extension, embeddings, tokenizer_load.
```

For offline CI runs:

```bash
docendo checkup --no-embedding --no-tokenizer
```

## 4. Run the pipeline

```bash
# Scrape RBI and download PDFs into data/raw/.
docendo fetch

# Extract, chunk, embed, and store in SQLite (data/processed/docendo.sqlite3).
docendo ingest

# Run 5 eval cases and write reports/results.jsonl.
docendo eval --limit 5

# Generate reports/eval_report.md from results.jsonl.
docendo report

# Launch the Streamlit A/B demo on http://localhost:8501.
docendo demo
```

## 5. Iterate

Re-running `docendo ingest` skips any PDF whose `content_hash` is
unchanged, so it makes zero embedding calls on an unchanged corpus. To
force re-embedding, delete the SQLite database (`rm
data/processed/docendo.sqlite3`) or remove specific rows by hand.

## Troubleshooting

- `ConfigurationError: tokenizer model does not match embedding model` —
  set `TOKENIZER_MODEL` to the same value as `VECTOR_MODEL`.
- `Embedding dim mismatch` — `VECTOR_DIMS` differs from the endpoint's
  actual dimension. Run `docendo checkup` with embedding enabled to
  observe the live dimension, then update `.env`.
- Slow ingestion — embedding API latency dominates. Run with a small
  `FETCH_MAX_DOCS` to size the corpus.
