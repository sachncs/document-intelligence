# Installation

## Requirements

- Python 3.11 or newer.
- macOS (x86_64 / arm64), glibc Linux (x86_64 / aarch64), or Windows x86_64.
  Alpine / musl and Windows ARM are not supported — see
  `docs/known-gaps.md`.
- An OpenAI-compatible endpoint serving `Qwen/Qwen3-Embedding-8B`.
- A MiniMax API key.

## Install from source

```bash
git clone <repo-url>
cd document-intelligence
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

`pip install -e .` (without `[dev]`) installs runtime only.

## Environment variables

Copy `.env.example` to `.env` and fill in real values:

```dotenv
# Chat model
MINIMAX_BASE_URL=https://api.minimax.io/v1
MINIMAX_API_KEY=sk-replace-with-your-real-key
MINIMAX_MODEL=MiniMax-M3

# Embeddings (Qwen3-Embedding-8B via an OpenAI-compatible endpoint)
BFSI_EMBEDDING_API_KEY=replace-with-your-embedding-key
BFSI_EMBEDDING_API_BASE=https://your-qwen-endpoint.example.com
BFSI_EMBEDDING_MODEL=Qwen/Qwen3-Embedding-8B
BFSI_TOKENIZER_MODEL=Qwen/Qwen3-Embedding-8B
BFSI_EMBEDDING_DIMS=4096

# Pipeline knobs (optional — defaults shown)
RBI_FETCH_MAX_DOCS=120
BFSI_CHUNK_SIZE_TOKENS=384
BFSI_CHUNK_OVERLAP_TOKENS=64
BFSI_EVAL_CONCURRENCY=5
BFSI_EVAL_LIMIT=40
BFSI_LOG_LEVEL=INFO
BFSI_HTTP_TIMEOUT=30
```

The full list of knobs lives in `src/docendo/config.py::Settings`.

## Verify the install

```bash
docendo doctor
```

For offline CI:

```bash
docendo doctor --no-embedding --no-tokenizer
```

## Troubleshooting

- `pip install` fails on sqliteai-vector — check that your platform has a
  prebuilt wheel. Alpine / musl is unsupported; rebuild a Python with
  glibc.
- `gigatoken` model downloads on first use — pre-warm by running
  `docendo doctor` with the embedding endpoint reachable.
