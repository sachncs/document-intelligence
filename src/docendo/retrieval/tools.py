"""Pydantic AI tool functions exposed to the agent.

Each function delegates to the cached :class:`Store` and returns the typed
contract defined in :mod:`docendo.retrieval.types`. Pydantic AI builds the
JSON schema from the type hints and docstrings, so no manual schema work
is needed.

Tools use single-word names (search, fetch, recent, compare). "Not found"
returns raise a sentinel via the marker dict; downstream tools return a
dict shaped like a successful response with ``found: False``.
"""

from __future__ import annotations

from typing import Any

from docendo.retrieval.types import (
    Document,
    Pair,
    PairResult,
    Query,
    Lookup,
    Recent,
)


def search(query: str, limit: int = 10) -> dict[str, Any]:
    """Search the corpus with hybrid BM25 + vector ranking.

    Args:
        query: natural-language question or topic (1-512 chars).
        limit: maximum hits to return (1-20, default 10).

    Returns:
        A dict with ``query`` and a list of ranked hits.
    """
    from docendo.retrieval._internal import get

    inp = Query(query=query, limit=limit)
    resp = get().hybrid_search(inp.query, inp.limit)
    return resp.model_dump(mode="json")


def fetch(id: str) -> dict[str, Any]:
    """Fetch all chunks of a specific document by its ID.

    Args:
        id: circular identifier (e.g. ``RBI/2023-24/123``).
    """
    from docendo.retrieval._internal import get

    inp = Lookup(id=id)
    resp: Document | None = get().fetch(inp.id)
    if resp is None:
        return {"circular_id": inp.id, "chunks": [], "found": False}
    out = resp.model_dump(mode="json")
    out["found"] = True
    return out


def recent(since: str, limit: int = 20, include_unknown_date: bool = False) -> dict[str, Any]:
    """List documents issued on or after ``since``.

    Args:
        since: ISO date ``YYYY-MM-DD``.
        limit: maximum items (1-20, default 20).
        include_unknown_date: if True, include documents whose issue_date failed to parse.
    """
    from docendo.retrieval._internal import get

    inp = Recent(since=since, limit=limit, include_unknown_date=include_unknown_date)
    items = get().list_recent(inp.since, inp.limit, inp.include_unknown_date)
    return {
        "since": inp.since,
        "items": [it.model_dump(mode="json") for it in items],
    }


def compare(id_a: str, id_b: str) -> dict[str, Any]:
    """Side-by-side comparison of two documents.

    Args:
        id_a: first document ID.
        id_b: second document ID.
    """
    from docendo.retrieval._internal import get

    inp = Pair(id_a=id_a, id_b=id_b)
    resp: PairResult | None = get().compare(inp.id_a, inp.id_b)
    if resp is None:
        return {"found": False, "id_a": inp.id_a, "id_b": inp.id_b}
    out = resp.model_dump(mode="json")
    out["found"] = True
    return out


__all__ = ["compare", "fetch", "recent", "search"]
