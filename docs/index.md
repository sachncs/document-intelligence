# Welcome to docendo

A grounded RAG agent for document intelligence over RBI circulars, master
directions, and policy documents.

Built on:

- **[Pydantic AI](https://ai.pydantic.dev)** — type-safe agent framework
- **[LiteLLM](https://litellm.vercel.app)** — provider-agnostic LLM client
- **[MiniMax-M3](https://platform.minimax.io)** — frontier multimodal model
- **[Qwen3-Embedding-8B](https://huggingface.co/Qwen/Qwen3-Embedding-8B)** — embedding model
- **[SQLite + sqlite-vector](https://github.com/sqliteai/sqlite-vector)** — local hybrid search

## Why

Regulated environments require answers grounded in official documents (RBI
circulars, master directions, FAQs). Generic LLMs hallucinate — for
compliance use, this is unacceptable. docendo:

1. Retrieves only from a curated corpus of RBI documents.
2. Forces every claim to carry a citation (circular_id, excerpt, URL).
3. Refuses clearly when out-of-scope.
4. Measures hallucination rate against an ungrounded baseline.

## Quick links

- [Installation](installation.md)
- [Quickstart](quickstart.md)
- [Architecture](architecture.md)
- [Evaluation](evaluation.md)
- [API Reference](api/agent.md)
