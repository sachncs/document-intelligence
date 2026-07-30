# Known gaps

This release of `docendo` ships with a single retrieval backend (local SQLite +
FTS5 + sqlite-vector) and a single agent runtime (Pydantic AI with direct
tools). The following items are deliberately deferred.

## Elastic backend

The previous Elasticsearch + Agent Builder path was removed entirely in
`v0.2.0`. If you need it back, see `docs/agent-builder-attach.md` for the
manual steps. The plan does **not** include automated re-introduction of the
Elastic backend until the authenticated MCP server (see below) is in place.

## Authenticated MCP server

`docendo` exposes its four retrieval tools to the in-process Pydantic AI
agent via direct tool functions. There is no `docendo serve-mcp` command,
no bearer-token middleware, and no public HTTPS endpoint yet.

The future server would:

- Run the same `docendo.retrieval.tools` functions behind a `mcp.server.fastmcp.FastMCP` instance.
- Listen on streamable HTTP for an authenticated external consumer.
- Issue a single bearer token from a secret manager and rotate it on demand.

Until then, the agent remains in-process. There is nothing to attach to
Elastic Agent Builder.

## Agent Builder attach

`docs/agent-builder-attach.md` walks through the manual Kibana steps required
to point Agent Builder at an external MCP server. The connector creation and
bulk tool import are **UI-driven** today because the Kibana connector API is
preview-only on Serverless and Elastic Stack 9.3+. When the server-side MCP
landed in `docendo` (see above), this guide would be updated with concrete
URLs and tokens.

## Public HTTPS host

The plan says the SQLite database can be hosted anywhere that exposes an
authenticated HTTPS MCP endpoint. We have **not** built a Dockerfile, a
compose file, a systemd unit, or a deployment runbook in this release.
Local-only operation is the default; production deployment is operator-
specific.

## `docendo update-corpus`

A "swap the database atomically" command does not exist. To roll out a new
corpus:

1. Build a new SQLite database on the host (or pull a prebuilt file).
2. Stop any process reading the existing database.
3. Replace `data/processed/rbi-circulars.sqlite3` with the new file.
4. Restart the agent / demo / evaluation runner.

Atomic file swaps with a symlink and SHA-256 check are a follow-up.

## Native sdist for `sqliteai-vector`

The `sqliteai-vector` PyPI package ships platform-specific wheels but no
source distribution. As of `0.2.0` we support macOS (x86/ARM), glibc Linux
(x86/ARM), and Windows (x86-64). Alpine / musl Linux and Windows ARM are
unsupported until upstream publishes matching wheels. If you need them,
consider vendoring `sqlite-vector`'s C source under a build hook.
