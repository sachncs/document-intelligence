"""docendo: grounded RAG agent for document intelligence."""

from __future__ import annotations

from importlib import metadata as _metadata

try:
    __version__ = _metadata.version("docendo")
except _metadata.PackageNotFoundError:  # pragma: no cover
    __version__ = "0.3.0a1"

__all__ = ["__version__"]
