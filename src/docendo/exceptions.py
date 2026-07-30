"""Custom exception hierarchy."""


from __future__ import annotations


class BFSIRBIError(Exception):
    """Root exception for all docendo errors."""


class ConfigurationError(BFSIRBIError):
    """Missing or invalid configuration."""


class ScrapingError(BFSIRBIError):
    """Failed to scrape RBI site."""


class PDFExtractionError(BFSIRBIError):
    """Failed to extract text from a PDF (both text and vision paths failed)."""


class VisionAPIError(BFSIRBIError):
    """Vision API call failed or returned invalid response."""


class EmbeddingProviderError(BFSIRBIError):
    """Embedding provider call failed or returned invalid output."""


class StorageError(BFSIRBIError):
    """SQLite or other storage backend failed."""


class EvalError(BFSIRBIError):
    """Evaluation pipeline failed."""
