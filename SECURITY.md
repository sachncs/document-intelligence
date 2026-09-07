# Security Policy

## Scope

This package is a **research and demonstration project** for grounded retrieval-augmented generation against publicly available RBI (Reserve Bank of India) circulars. It is **not** a production compliance system and must not be used as the sole basis for any financial, regulatory, or legal decision.

## Reporting vulnerabilities

If you discover a security issue, please email `[email protected]`. Do not open a public GitHub issue.

## Known limitations

- LLM-generated answers can be wrong even when citations look correct. Always verify against the source RBI circular.
- The retrieval corpus is bounded and may not reflect the most recent amendments.
- Vision-based PDF extraction can introduce transcription errors.
- The agent's tool calls are scoped to its Elasticsearch API key; an attacker with API key access could read or corrupt the index.

## Scope of responsibility

The maintainers make no warranty as to the fitness of this software for any particular purpose. Use at your own risk.
