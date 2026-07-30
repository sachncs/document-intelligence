"""Pydantic AI tool functions exposed to the agent.

Each function delegates to the cached :class:`SQLiteStore` and returns the
typed contract defined in :mod:`docendo.retrieval.types`. Pydantic AI builds
the JSON schema from the type hints and docstrings, so no manual schema work
is needed.
"""

from __future__ import annotations

from typing import Any

from docendo.retrieval.types import (
    CircularResponse,
    CompareInput,
    CompareResponse,
    GetCircularInput,
    HybridSearchInput,
    ListRecentInput,
    RecentItem,
    SearchResponse,
)


def hybrid_search(query: str, limit: int = 10) -> dict[str, Any]:
    """Search the RBI corpus with hybrid BM25 + vector ranking.

    Args:
        query: natural-language question or topic (1-512 chars).
        limit: maximum hits to return (1-20, default 10).

    Returns:
        A dict with ``query`` and a list of ranked hits.
    """
    from docendo.retrieval.factory import get_retriever

    inp = HybridSearchInput(query=query, limit=limit)
    resp: SearchResponse = get_retriever().hybrid_search(inp.query, inp.limit)
    return resp.model_dump(mode="json")


def get_circular(id: str) -> dict[str, Any]:
    """Fetch all chunks of a specific RBI circular by its ID.

    Args:
        id: circular identifier (e.g. ``RBI/2023-24/123``).
    """
    from docendo.retrieval.factory import get_retriever

    inp = GetCircularInput(id=id)
    resp: CircularResponse | None = get_retriever().get_circular(inp.id)
    if resp is None:
        return {"circular_id": inp.id, "chunks": [], "found": False}
    out = resp.model_dump(mode="json")
    out["found"] = True
    return out


def list_recent(since: str, limit: int = 20) -> dict[str, Any]:
    """List RBI circulars issued on or after ``since``.

    Args:
        since: ISO date ``YYYY-MM-DD``.
        limit: maximum items (1-20, default 20).
    """
    from docendo.retrieval.factory import get_retriever

    inp = ListRecentInput(since=since, limit=limit)
    items: list[RecentItem] = get_retriever().list_recent(inp.since, inp.limit)
    return {"since": inp.since, "items": [it.model_dump(mode="json") for it in items]}


def compare_circulars(id_a: str, id_b: str) -> dict[str, Any]:
    """Side-by-side comparison of two circulars.

    Args:
        id_a: first circular ID.
        id_b: second circular ID.
    """
    from docendo.retrieval.factory import get_retriever

    inp = CompareInput(id_a=id_a, id_b=id_b)
    resp: CompareResponse | None = get_retriever().compare(inp.id_a, inp.id_b)
    if resp is None:
        return {"found": False, "id_a": inp.id_a, "id_b": inp.id_b}
    out = resp.model_dump(mode="json")
    out["found"] = True
    return out


__all__ = [
    "compare_circulars",
    "get_circular",
    "hybrid_search",
    "list_recent",
]
