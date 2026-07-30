# Security

## Secrets

`docendo` reads four secrets at runtime:

- `CHAT_KEY` — the chat model API key.
- `VECTOR_KEY` — the embedding endpoint API key.
- `VECTOR_BASE` — the OpenAI-compatible base URL serving
  Qwen3-Embedding-8B.
- (future) bearer token for the authenticated MCP server.

Always:

- Keep secrets out of source control. `.env` is git-ignored by default.
- Use `chmod 600 .env` on shared hosts.
- Prefer a secret manager (1Password, AWS Secrets Manager, Vault) for
  production deployments. `docendo` reads from the process environment, so
  any loader that injects env vars works.

## Network egress

`docendo` makes outbound requests to:

- The RBI website (HTTPS) for PDF download during `docendo fetch`.
- The embedding endpoint (HTTPS) for chunk encoding.
- The chat model endpoint (HTTPS) for LLM calls.
- The vision endpoint (HTTPS) for scanned-PDF fallback extraction.

No other endpoints are contacted. No telemetry leaves the host.

## Local SQLite file

- The SQLite database contains indexed chunks of public RBI documents. No
  user data is stored.
- Restrict filesystem permissions: `chmod 600 data/processed/docendo.sqlite3`.
- Back up before any manual rebuild; there is no recovery path from a
  truncated write.

## FTS5 query handling

User queries are passed to the FTS5 `MATCH` operator wrapped in double
quotes, with embedded double quotes doubled. This prevents FTS5 syntax
errors from operator injection (`AND`, `OR`, `NOT`) and limits the
searchable surface to literal tokens. See
`src/docendo/retrieval/store.py::Store::fts_escape`.

## Embedding cache

The embedding layer maintains a process-local LRU cache of up to 8192
vectors. Cached entries are keyed by `(model, dims, sha256(text))`. No
text content is logged or exposed via any debug endpoint.

## CVE reporting

Report security issues to the maintainers via the project's GitHub
repository's "Security" tab. Do not file public issues for vulnerabilities.
