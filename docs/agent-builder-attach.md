# Attaching `docendo` to Elastic Agent Builder

> This guide is a placeholder. As of `v0.2.0` `docendo` does **not** expose
> an authenticated MCP server. The agent uses direct Python tools in-process,
> and Elastic Agent Builder external-MCP support is in preview on Serverless and
> Elastic Stack 9.3+. When the MCP server ships, this page will be updated with
> concrete Kibana clicks and connector configuration.

## Why this is a placeholder

Elastic Agent Builder can call **external** MCP tools, but doing so requires:

1. A network-reachable MCP server speaking the streamable HTTP transport.
2. A bearer token or API key the connector can attach to every request.
3. A Kibana MCP connector pointing at that server.

`docendo v0.2.0` has none of those — the SQLite store runs in the same
process as the agent, behind four direct tool functions.

## When this guide becomes actionable

After `docendo` ships:

- A `serve-mcp` CLI command that exposes the four retrieval tools over
  streamable HTTP.
- A bearer-token middleware in front of the HTTP endpoint.
- A documented deployment topology (Dockerfile, systemd unit, or similar)
  with persistent volume for the SQLite file.

The `docendo attach-ab` command will then:

- `initialize` against the public MCP URL.
- Send `tools/list` and assert the four `rbi.*` tools are present.
- Print the manual Kibana steps to import them under the `rbi.` namespace.

## Manual Kibana steps (for later)

Once the MCP server is live:

1. Kibana → Stack Management → Connectors → Create Connector → MCP.
2. Set Server URL to `BFSI_MCP_PUBLIC_URL`.
3. Add a Secret header `Authorization: Bearer <token>`.
4. Run the connector's `test`, then `listTools`.
5. Tools page → Bulk import MCP tools, namespace `rbi`, all four.
6. Repoint the `rbi-policy-analyst` agent at the four imported tool IDs.

## Pinning an Agent Builder version

External MCP tools are GA on Elastic Cloud Serverless and Elastic Stack 9.4+
(with preview on 9.3). Pin your deployment before relying on this guide.
