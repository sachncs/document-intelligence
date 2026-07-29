"""Custom exception hierarchy."""

from __future__ import annotations


class BFSIRBIError(Exception):
    """Root exception for all bfsi-rbi errors."""


class ConfigurationError(BFSIRBIError):
    """Missing or invalid configuration."""


class ScrapingError(BFSIRBIError):
    """Failed to scrape RBI site."""


class PDFExtractionError(BFSIRBIError):
    """Failed to extract text from a PDF (both text and vision paths failed)."""


class VisionAPIError(BFSIRBIError):
    """Vision API call failed or returned invalid response."""


class ElasticsearchError(BFSIRBIError):
    """Elasticsearch operation failed."""


class AgentBuilderError(BFSIRBIError):
    """Agent Builder API call failed."""


class MCPConnectionError(BFSIRBIError):
    """Could not connect to the Agent Builder MCP server."""


class EvalError(BFSIRBIError):
    """Evaluation pipeline failed."""
