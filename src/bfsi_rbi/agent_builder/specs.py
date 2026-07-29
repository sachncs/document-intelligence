"""Agent Builder tool and agent JSON specs.

These are the canonical definitions POSTed to the Kibana Agent Builder
API. Keep them as Python ``dict``s so they're version-controlled and
lintable.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Tool: hybrid search (BM25 + semantic) via FORK / FUSE RRF
# ---------------------------------------------------------------------------
hybrid_search_tool: dict[str, Any] = {
    "id": "rbi.hybrid_search",
    "type": "esql",
    "description": (
        "Hybrid search RBI circulars using BM25 + ELSER semantic (RRF-fused). "
        "Always call this tool first when answering a question about RBI policy. "
        "Returns up to ?limit chunks with circular_id, title, text, score, and source_url."
    ),
    "tags": ["rbi", "search", "hybrid"],
    "configuration": {
        "query": (
            "FROM rbi-circulars METADATA _score "
            "| FORK ("
            "  WHERE match(text, ?query) | LIMIT 20"
            ") ("
            "  WHERE semantic_text:semantic_field(?query) | LIMIT 20"
            ") "
            "| FUSE RRF "
            "| LIMIT ?limit"
        ),
        "params": {
            "query": {
                "type": "string",
                "description": "Natural-language search query.",
            },
            "limit": {
                "type": "integer",
                "optional": True,
                "defaultValue": 10,
                "description": "Maximum number of chunks to return.",
            },
        },
    },
}

# ---------------------------------------------------------------------------
# Tool: fetch a single circular by ID
# ---------------------------------------------------------------------------
get_circular_tool: dict[str, Any] = {
    "id": "rbi.get_circular",
    "type": "esql",
    "description": (
        "Fetch a single RBI circular by its circular_id. "
        "Returns all chunks concatenated in order. Use this when the user "
        "names a specific circular or when you need the full text of a circular "
        "found via hybrid_search."
    ),
    "tags": ["rbi", "fetch"],
    "configuration": {
        "query": (
            "FROM rbi-circulars "
            "| WHERE circular_id == ?id "
            "| SORT chunk_index ASC "
            "| KEEP circular_id, title, text, issue_date, topic, source_url, chunk_index, chunk_count"
        ),
        "params": {
            "id": {
                "type": "string",
                "description": "The circular_id to fetch.",
            },
        },
    },
}

# ---------------------------------------------------------------------------
# Tool: list recent circulars (date-filtered)
# ---------------------------------------------------------------------------
list_recent_tool: dict[str, Any] = {
    "id": "rbi.list_recent",
    "type": "esql",
    "description": (
        "List the most recent RBI circulars issued on or after a given date. "
        "Use this for questions about recent amendments, new rules, or to "
        "discover what is in the corpus."
    ),
    "tags": ["rbi", "list", "recent"],
    "configuration": {
        "query": (
            "FROM rbi-circulars "
            "| WHERE issue_date >= ?since AND chunk_index == 0 "
            "| SORT issue_date DESC "
            "| LIMIT ?limit "
            "| KEEP circular_id, title, issue_date, topic, source_url"
        ),
        "params": {
            "since": {
                "type": "date",
                "description": "Earliest issue_date to include (ISO 8601).",
            },
            "limit": {
                "type": "integer",
                "optional": True,
                "defaultValue": 20,
                "description": "Maximum circulars to return.",
            },
        },
    },
}

# ---------------------------------------------------------------------------
# Tool: compare two circulars side-by-side
# ---------------------------------------------------------------------------
compare_circulars_tool: dict[str, Any] = {
    "id": "rbi.compare_circulars",
    "type": "esql",
    "description": (
        "Compare two RBI circulars by their circular_id. Returns both "
        "concatenated, separated by a divider. Use this when the user asks "
        "to compare rules across entity types or time periods."
    ),
    "tags": ["rbi", "compare"],
    "configuration": {
        "query": (
            "FROM rbi-circulars "
            "| WHERE circular_id == ?id_a OR circular_id == ?id_b "
            "| SORT circular_id ASC, chunk_index ASC "
            "| KEEP circular_id, title, text, issue_date, source_url, chunk_index"
        ),
        "params": {
            "id_a": {"type": "string", "description": "First circular_id."},
            "id_b": {"type": "string", "description": "Second circular_id."},
        },
    },
}

TOOL_SPECS: list[dict[str, Any]] = [
    hybrid_search_tool,
    get_circular_tool,
    list_recent_tool,
    compare_circulars_tool,
]

# ---------------------------------------------------------------------------
# Agent: RBI Policy Analyst
# ---------------------------------------------------------------------------
AGENT_SPEC: dict[str, Any] = {
    "id": "rbi-policy-analyst",
    "name": "RBI Policy Analyst",
    "description": (
        "Grounded analyst for RBI circulars, master directions, and policy "
        "documents. Always cites its sources; refuses when out-of-scope."
    ),
    "labels": ["bfsi", "rbi", "policy"],
    "avatar_color": "#1E40AF",
    "avatar_symbol": "RBI",
    "configuration": {
        "instructions": (
            "You are an expert RBI Policy Analyst. Use the `rbi.*` tools to "
            "ground every answer in the official RBI corpus. Cite every "
            "factual claim with the circular_id, an excerpt, and a source "
            "URL on rbi.org.in. If the corpus does not contain a relevant "
            "circular, refuse clearly and set confidence to 'low'."
        ),
        "tools": [
            {"tool_ids": [tool["id"] for tool in TOOL_SPECS]},
        ],
    },
}


__all__ = [
    "AGENT_SPEC",
    "TOOL_SPECS",
    "compare_circulars_tool",
    "get_circular_tool",
    "hybrid_search_tool",
    "list_recent_tool",
]
