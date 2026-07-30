"""RBI document ingestion subsystem."""

from docendo.ingestion.pdf import (
    extract_pdf,
    extract_text_via_vision,
    render_page_to_png,
)
from docendo.ingestion.pipeline import IngestionReport, run_ingestion
from docendo.ingestion.rbi_scraper import (
    DiscoveredDocument,
    DiscoveredMasterDirection,
    rbi_url,
    scrape_index_pages,
)
from docendo.models import ExtractedDocument

__all__ = [
    "DiscoveredDocument",
    "DiscoveredMasterDirection",
    "ExtractedDocument",
    "IngestionReport",
    "extract_pdf",
    "extract_text_via_vision",
    "rbi_url",
    "render_page_to_png",
    "run_ingestion",
    "scrape_index_pages",
]
