"""docendo retrieval subsystem.

Public surface:
- Store: SQLite + FTS5 + sqlite-vector backend
- Query/Lookup/Recent/Pair: input models
- Hit/Results/Document/Listing/PairResult: output models
- search/fetch/recent/compare: the four Pydantic AI tool functions
- chunk: gigatoken chunking
- aembed: LiteLLM embedding client
"""

from docendo.retrieval.chunker import chunk
from docendo.retrieval.embedder import aembed
from docendo.retrieval._internal import get, reset
from docendo.retrieval.store import Store
from docendo.retrieval.tools import compare, fetch, recent, search
from docendo.retrieval.types import (
    Document,
    Hit,
    Listing,
    Lookup,
    Pair,
    PairResult,
    Query,
    Recent,
    Results,
)

__all__ = [
    "Document",
    "Hit",
    "Listing",
    "Lookup",
    "Pair",
    "PairResult",
    "Query",
    "Recent",
    "Results",
    "Store",
    "aembed",
    "chunk",
    "compare",
    "fetch",
    "get",
    "recent",
    "reset",
    "search",
]
