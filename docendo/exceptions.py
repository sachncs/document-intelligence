"""docendo custom exception hierarchy."""


from __future__ import annotations


class Error(Exception):
    """Root exception for all docendo errors."""


class ConfigurationError(Error):
    """Missing or invalid configuration."""


class ScrapingError(Error):
    """Failed to scrape the upstream site."""


class PDFExtractionError(Error):
    """Failed to extract text from a PDF (both text and vision paths failed)."""


class VisionAPIError(Error):
    """Vision API call failed or returned invalid response."""


class EmbeddingProviderError(Error):
    """Embedding provider call failed or returned invalid output."""


class StorageError(Error):
    """SQLite or other storage backend failed."""


class EvalError(Error):
    """Evaluation pipeline failed."""


__all__ = [
    "ConfigurationError",
    "EmbeddingProviderError",
    "Error",
    "EvalError",
    "PDFExtractionError",
    "ScrapingError",
    "StorageError",
    "VisionAPIError",
]
