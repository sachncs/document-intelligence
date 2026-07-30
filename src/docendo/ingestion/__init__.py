"""docendo ingestion subsystem."""

from docendo.ingestion.ingest import Report, run
from docendo.ingestion.reader import (
    Page,
    Record,
    read,
    read_page,
    render_page,
)
from docendo.ingestion.scraper import (
    Direction,
    Found,
    discover,
    download,
    scrape,
    url,
)

__all__ = [
    "Direction",
    "Found",
    "Page",
    "Record",
    "Report",
    "discover",
    "download",
    "read",
    "read_page",
    "render_page",
    "run",
    "scrape",
    "url",
]
