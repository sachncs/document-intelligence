# Known gaps

This release of `docendo` ships with a single retrieval backend (local SQLite +
FTS5 + sqlite-vector) and a single agent runtime (Pydantic AI with direct
tools). The following items are deliberately deferred.

## MCP server

`docendo` exposes its four retrieval tools to the in-process Pydantic AI
agent via direct tool functions. There is no `docendo serve-mcp` command,
no bearer-token middleware, and no public HTTPS endpoint yet.

When the MCP server ships, it will:

- Run the same `docendo.retrieval.tools` functions behind a `mcp.server.fastmcp.FastMCP` instance.
- Listen on streamable HTTP for an authenticated external consumer.
- Issue a single bearer token from a secret manager and rotate it on demand.

## Agent Builder attach

`docs/agent-builder-attach.md` is a placeholder. Agent Builder external
MCP tools are in preview on Serverless and Elastic Stack 9.3+; the
connector creation and bulk tool import are UI-driven today. When the
MCP server lands in `docendo`, that guide will be updated with concrete
URLs and tokens.

## Elastic backend (historical)

The previous Elasticsearch + Agent Builder + ES|QL backend was removed
in `v0.2.0`. It will return when the MCP server does; until then, the
SQLite store is the only retrieval path.

## Public HTTPS host

The plan says the SQLite database can be hosted anywhere that exposes an
authenticated HTTPS MCP endpoint. We have **not** built a Dockerfile,
compose file, systemd unit, or deployment runbook in this release.
Local-only operation is the default; production deployment is
operator-specific.

## `update-corpus`

A "swap the database atomically" command does not exist. To roll out a
new corpus:

1. Build a new SQLite database on the host (or pull a prebuilt file).
2. Stop any process reading the existing database.
3. Replace `data/processed/docendo.sqlite3` with the new file.
4. Restart the agent / demo / evaluation runner.

Atomic file swaps with a symlink and SHA-256 check are a follow-up.

## `rrf_k` UI exposure

`Settings.rrf_k` controls the RRF fusion denominator. It is documented and
tested but not yet exposed as a CLI flag. Add `--rrf-k` to `bfsi-rbi ingest`
in a follow-up.

## Tool return-shape enforcement

The four tool functions return dicts that conform to the typed
contract, but the contract is not enforced at the tool boundary by
Pydantic AI today. Add a tool-output validator in a follow-up.

## Native sdist for `sqliteai-vector`

The `sqliteai-vector` PyPI package ships platform-specific wheels but no
source distribution. As of `0.3.0a1` we support macOS (x86/ARM), glibc
Linux (x86/ARM), and Windows (x86-64). Alpine / musl and Windows ARM are
unsupported until upstream publishes matching wheels.
