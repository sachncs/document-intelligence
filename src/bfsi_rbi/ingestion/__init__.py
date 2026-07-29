"""RBI document ingestion subsystem."""

from bfsi_rbi.ingestion.pdf import (
    extract_pdf,
    extract_text_via_vision,
    render_page_to_png,
)
from bfsi_rbi.ingestion.pipeline import IngestionReport, run_ingestion
from bfsi_rbi.ingestion.rbi_scraper import (
    DiscoveredDocument,
    DiscoveredMasterDirection,
    rbi_url,
    scrape_index_pages,
)
from bfsi_rbi.models import ExtractedDocument

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
