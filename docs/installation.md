# Installation

## Requirements

- Python 3.11 or newer.
- macOS (x86_64 / arm64), glibc Linux (x86_64 / aarch64), or Windows x86-64.
  Alpine / musl and Windows ARM are not supported — see `KNOWN_GAPS.md`.
- An OpenAI-compatible endpoint serving `Qwen/Qwen3-Embedding-8B`.
- A MiniMax API key.

## Install from source

```bash
git clone https://github.com/sachncs/document-intelligence
cd docendo
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

`pip install -e .` (without `[dev]`) installs runtime only.

## Environment variables

Copy `.env.example` to `.env` and fill in real values:

```dotenv
# Chat model
CHAT_URL=https://api.minimax.io/v1
CHAT_KEY=sk-replace-with-your-real-key
CHAT_MODEL=MiniMax-M3
CHAT_TIMEOUT=60

# Embeddings (Qwen3-Embedding-8B via an OpenAI-compatible endpoint)
VECTOR_PROVIDER=openai_compatible
VECTOR_MODEL=Qwen/Qwen3-Embedding-8B
VECTOR_DIMS=4096
VECTOR_KEY=replace-with-your-embedding-key
VECTOR_BASE=https://your-qwen-endpoint.example.com
VECTOR_BATCH=64
TOKENIZER_MODEL=Qwen/Qwen3-Embedding-8B
TOKENIZER_ALLOW_MISMATCH=0

# Chunking (gigatoken tokens)
CHUNK_SIZE=384
CHUNK_OVERLAP=64
CHUNK_MAX_CHARS=400

# Retrieval
STORE_PATH=data/processed/docendo.sqlite3
RRF_K=60

# Fetch and eval
FETCH_MAX_DOCS=120
EVAL_CONCURRENCY=5
EVAL_LIMIT=40

# Tooling
LOG_LEVEL=INFO
HTTP_TIMEOUT=30

# CI hooks (do not delete)
# RUN_PERF=1 to enable perf benchmarks (see tests/perf/)
# RUN_INTEGRATION=1 to enable integration tests against live services
```

The full list of knobs lives in `src/docendo/config.py::Settings`.

## Verify the install

```bash
docendo checkup
```

For offline CI:

```bash
docendo checkup --no-embedding --no-tokenizer
```

## Troubleshooting

- `pip install` fails on sqliteai-vector — check that your platform has a
  prebuilt wheel. Alpine / musl is unsupported; rebuild a Python with
  glibc.
- `gigatoken` model downloads on first use — pre-warm by running
  `docendo checkup` with the embedding endpoint reachable.
