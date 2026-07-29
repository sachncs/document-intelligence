"""Agent Builder deploy + smoke-test helpers.

Talks to the Kibana ``/api/agent_builder/*`` REST endpoints.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from bfsi_rbi.agent_builder.specs import AGENT_SPEC, TOOL_SPECS
from bfsi_rbi.config import Settings, get_settings
from bfsi_rbi.exceptions import AgentBuilderError, MCPConnectionError
from bfsi_rbi.logging import get_logger

logger = get_logger(__name__)


def _kibana_headers(settings: Settings) -> dict[str, str]:
    return {
        "Authorization": f"ApiKey {settings.elastic_api_key}",
        "kbn-xsrf": "true",
        "Content-Type": "application/json",
    }


def _kibana_base(settings: Settings) -> str:
    return settings.elastic_url.rstrip("/")


def _post(path: str, body: dict[str, Any], settings: Settings) -> dict[str, Any]:
    settings.require_elastic()
    url = f"{_kibana_base(settings)}{path}"
    try:
        with httpx.Client(timeout=settings.bfsi_http_timeout) as client:
            r = client.post(url, headers=_kibana_headers(settings), json=body)
            r.raise_for_status()
            return dict(r.json()) if r.content else {}
    except httpx.HTTPError as exc:
        raise AgentBuilderError(f"POST {url} failed: {exc}") from exc


def _put(path: str, body: dict[str, Any], settings: Settings) -> dict[str, Any]:
    settings.require_elastic()
    url = f"{_kibana_base(settings)}{path}"
    try:
        with httpx.Client(timeout=settings.bfsi_http_timeout) as client:
            r = client.put(url, headers=_kibana_headers(settings), json=body)
            r.raise_for_status()
            return dict(r.json()) if r.content else {}
    except httpx.HTTPError as exc:
        raise AgentBuilderError(f"PUT {url} failed: {exc}") from exc


def _delete(path: str, settings: Settings) -> None:
    settings.require_elastic()
    url = f"{_kibana_base(settings)}{path}"
    try:
        with httpx.Client(timeout=settings.bfsi_http_timeout) as client:
            r = client.delete(url, headers=_kibana_headers(settings))
            r.raise_for_status()
    except httpx.HTTPError as exc:
        raise AgentBuilderError(f"DELETE {url} failed: {exc}") from exc


def _get(path: str, settings: Settings) -> dict[str, Any]:
    settings.require_elastic()
    url = f"{_kibana_base(settings)}{path}"
    try:
        with httpx.Client(timeout=settings.bfsi_http_timeout) as client:
            r = client.get(url, headers=_kibana_headers(settings))
            r.raise_for_status()
            return dict(r.json()) if r.content else {}
    except httpx.HTTPError as exc:
        raise AgentBuilderError(f"GET {url} failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Tool deploy
# ---------------------------------------------------------------------------
def deploy_tools(
    settings: Settings | None = None,
    specs: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Idempotently POST all tool specs to Kibana.

    Uses POST (create) first; on 409 conflict, falls back to PUT (update).
    """
    settings = settings or get_settings()
    target_specs = specs or TOOL_SPECS
    results: list[dict[str, Any]] = []
    for spec in target_specs:
        tool_id = spec["id"]
        path = "/api/agent_builder/tools"
        try:
            create_body = {
                "id": tool_id,
                "type": spec["type"],
                "description": spec["description"],
                "tags": spec.get("tags", []),
                "configuration": spec["configuration"],
            }
            result = _post(path, create_body, settings)
        except AgentBuilderError:
            update_path = f"/api/agent_builder/tools/{tool_id}"
            update_body = {
                "description": spec["description"],
                "tags": spec.get("tags", []),
                "configuration": spec["configuration"],
            }
            result = _put(update_path, update_body, settings)
        results.append({"id": tool_id, "result": result})
        logger.info("Deployed tool %s", tool_id)
    return results


def delete_tool(tool_id: str, settings: Settings | None = None) -> None:
    """Delete a single tool by ID."""
    settings = settings or get_settings()
    _delete(f"/api/agent_builder/tools/{tool_id}", settings)


def list_tools(settings: Settings | None = None) -> list[dict[str, Any]]:
    """List all Agent Builder tools."""
    settings = settings or get_settings()
    resp = _get("/api/agent_builder/tools", settings)
    results = resp.get("results", [])
    if isinstance(results, list):
        return results
    return []


# ---------------------------------------------------------------------------
# Agent deploy
# ---------------------------------------------------------------------------
def deploy_agent(
    settings: Settings | None = None,
    spec: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Idempotently POST the agent spec to Kibana."""
    settings = settings or get_settings()
    agent_spec = spec or AGENT_SPEC
    agent_id = agent_spec["id"]
    try:
        body = {
            "id": agent_id,
            "name": agent_spec["name"],
            "description": agent_spec["description"],
            "labels": agent_spec.get("labels", []),
            "avatar_color": agent_spec.get("avatar_color"),
            "avatar_symbol": agent_spec.get("avatar_symbol"),
            "configuration": agent_spec["configuration"],
        }
        result = _post("/api/agent_builder/agents", body, settings)
    except AgentBuilderError:
        update_path = f"/api/agent_builder/agents/{agent_id}"
        update_body = {
            "name": agent_spec["name"],
            "description": agent_spec["description"],
            "labels": agent_spec.get("labels", []),
            "avatar_color": agent_spec.get("avatar_color"),
            "avatar_symbol": agent_spec.get("avatar_symbol"),
            "configuration": agent_spec["configuration"],
        }
        result = _put(update_path, update_body, settings)
    logger.info("Deployed agent %s", agent_id)
    return {"id": agent_id, "result": result}


def delete_agent(agent_id: str, settings: Settings | None = None) -> None:
    """Delete a single agent by ID."""
    settings = settings or get_settings()
    _delete(f"/api/agent_builder/agents/{agent_id}", settings)


def list_agents(settings: Settings | None = None) -> list[dict[str, Any]]:
    """List all Agent Builder agents."""
    settings = settings or get_settings()
    resp = _get("/api/agent_builder/agents", settings)
    results = resp.get("results", [])
    if isinstance(results, list):
        return results
    return []


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------
def smoke_test_mcp(settings: Settings | None = None) -> dict[str, Any]:
    """Verify the MCP endpoint is reachable and returns the tools list.

    Sends an ``initialize`` MCP handshake via JSON-RPC over HTTP.
    """
    settings = settings or get_settings()
    if not settings.elastic_mcp_url:
        raise MCPConnectionError("ELASTIC_MCP_URL is not set")

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "bfsi-rbi", "version": "0.1.0"},
        },
    }
    headers = {
        "Authorization": f"ApiKey {settings.elastic_api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.post(settings.elastic_mcp_url, headers=headers, json=payload)
            r.raise_for_status()
            text = r.text
            if text.startswith("data:"):
                text = text.split("data:", 1)[1].strip()
            data = json.loads(text)
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        raise MCPConnectionError(f"MCP smoke test failed: {exc}") from exc

    logger.info("MCP handshake OK")
    return {"ok": True, "server": data.get("result", {}).get("serverInfo", {})}


__all__ = [
    "delete_agent",
    "delete_tool",
    "deploy_agent",
    "deploy_tools",
    "list_agents",
    "list_tools",
    "smoke_test_mcp",
]
