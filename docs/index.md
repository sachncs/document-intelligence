# Welcome to bfsi-rbi

A grounded RAG agent for BFSI (Banking, Financial Services, Insurance) document
intelligence over RBI circulars, master directions, and policy documents.

Built on:

- **[Pydantic AI](https://ai.pydantic.dev)** — type-safe agent framework
- **[Elastic Agent Builder](https://www.elastic.co/agent-builder)** — tools & MCP
- **[LiteLLM](https://litellm.vercel.app)** — provider-agnostic LLM client
- **[MiniMax-M3](https://platform.minimax.io)** — frontier multimodal model

## Why

Regulated BFSI environments require answers grounded in official documents
(RBI circulars, master directions, FAQs). Generic LLMs hallucinate — for
compliance use, this is unacceptable. bfsi-rbi:

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
