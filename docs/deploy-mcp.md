# Future: deploying the authenticated MCP server

> This guide is a placeholder. As of `v0.2.0` `docendo` does **not** expose
> an authenticated MCP server. The agent uses direct Python tools in-process.

## What will live here

When the MCP server ships (see `docs/known-gaps.md`), this page will document:

- `docendo serve-mcp` command-line flags and environment variables.
- Bearer-token generation, rotation, and storage in `pass` or a `.env` with
  `chmod 600`.
- A Caddy / Nginx / Cloudflare edge config for terminating TLS in front of
  the streamable HTTP listener.
- A `Dockerfile` and a `compose.yaml` for self-hosting.
- An example systemd unit for running the server as a long-lived service.
- How to point Elastic Agent Builder's MCP connector at the deployed URL.

For now, this file exists so that `mkdocs build --strict` passes and so
that future contributors can find the planned layout.
