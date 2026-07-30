"""RBI public-site scraper.

Fetches the index pages of RBI Master Directions, Master Circulars, and
recent standalone circulars, and extracts downloadable PDF links.

The RBI site is plain HTML tables — no JS, no auth.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from docendo.config import Settings, get_settings
from docendo.exceptions import ScrapingError
from docendo.logging import get_logger

logger = get_logger(__name__)

RBI_BASE = "https://www.rbi.org.in"

# Index pages we harvest
MASTER_DIRECTIONS_INDEX = "https://website.rbi.org.in/web-rules/notifications/master-directions"
MASTER_CIRCULARS_INDEX = "https://website.rbi.org.in/web-rules/notifications/master-circulars"
NOTIFICATIONS_INDEX = "https://www.rbi.org.in/Scripts/NotificationUser.aspx"


@dataclass(frozen=True)
class DiscoveredDocument:
    """A PDF document discovered on the RBI site."""

    circular_id: str  # derived from title or URL slug
    title: str
    pdf_url: str
    source_page: str
    topic: str  # "master_direction" | "master_circular" | "circular"


@dataclass(frozen=True)
class DiscoveredMasterDirection:
    """A master direction index entry (may have one or more PDFs)."""

    title: str
    detail_url: str
    pdf_url: str | None
    topic: str


def rbi_url(path: str) -> str:
    """Build an absolute RBI URL from a relative path."""
    return urljoin(RBI_BASE + "/", path.lstrip("/"))


def _http_get(url: str, settings: Settings) -> str:
    """Fetch a URL with retry, return text content."""
    headers = {
        "User-Agent": "docendo/0.1 (+research; not for production compliance)",
        "Accept": "text/html,application/pdf",
    }
    try:
        with httpx.Client(
            timeout=settings.bfsi_http_timeout,
            headers=headers,
            follow_redirects=True,
        ) as client:
            r = client.get(url)
            r.raise_for_status()
            return r.text
    except httpx.HTTPError as exc:
        raise ScrapingError(f"GET {url} failed: {exc}") from exc


def _safe_circular_id(title: str, url: str) -> str:
    """Derive a deterministic circular ID from a title or URL."""
    slug = re.sub(r"[^A-Za-z0-9]+", "-", title or url).strip("-")[:80]
    return slug or "rbi-doc"


def _parse_pdf_links(
    html: str, base_url: str, topic: str, max_docs: int
) -> list[DiscoveredDocument]:
    """Parse a table of notification links and return PDF entries."""
    soup = BeautifulSoup(html, "html.parser")
    results: list[DiscoveredDocument] = []
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if ".pdf" not in href.lower():
            continue
        title = link.get_text(strip=True) or href
        pdf_url = urljoin(base_url, href)
        if not pdf_url.startswith(("http://", "https://")):
            continue
        circular_id = _safe_circular_id(title, pdf_url)
        results.append(
            DiscoveredDocument(
                circular_id=circular_id,
                title=title,
                pdf_url=pdf_url,
                source_page=base_url,
                topic=topic,
            )
        )
        if len(results) >= max_docs:
            break
    return results


def scrape_index_pages(
    max_docs: int = 120,
    settings: Settings | None = None,
) -> list[DiscoveredDocument]:
    """Scrape RBI notification index pages and return up to ``max_docs`` PDFs."""
    settings = settings or get_settings()
    logger.info("Scraping RBI index pages (max_docs=%d)", max_docs)
    docs: list[DiscoveredDocument] = []

    for url, topic in (
        (MASTER_DIRECTIONS_INDEX, "master_direction"),
        (MASTER_CIRCULARS_INDEX, "master_circular"),
        (NOTIFICATIONS_INDEX, "circular"),
    ):
        if len(docs) >= max_docs:
            break
        try:
            html = _http_get(url, settings)
        except ScrapingError as exc:
            logger.warning("Skipping %s: %s", url, exc)
            continue
        new_docs = _parse_pdf_links(html, url, topic, max_docs - len(docs))
        docs.extend(new_docs)
        logger.info("Found %d PDFs at %s", len(new_docs), url)

    # Deduplicate by pdf_url
    seen: set[str] = set()
    unique: list[DiscoveredDocument] = []
    for d in docs:
        if d.pdf_url in seen:
            continue
        seen.add(d.pdf_url)
        unique.append(d)
    return unique[:max_docs]


def download_pdf(
    doc: DiscoveredDocument,
    target_dir: Path,
    settings: Settings | None = None,
) -> Path:
    """Download a PDF document to ``target_dir`` if absent."""
    settings = settings or get_settings()
    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", doc.circular_id)[:80] + ".pdf"
    target = target_dir / safe_name
    if target.exists() and target.stat().st_size > 0:
        return target

    try:
        with (
            httpx.Client(
                timeout=settings.bfsi_http_timeout,
                follow_redirects=True,
                headers={"User-Agent": "docendo/0.1"},
            ) as client,
            client.stream("GET", doc.pdf_url) as r,
        ):
            r.raise_for_status()
            with target.open("wb") as fh:
                for chunk in r.iter_bytes():
                    fh.write(chunk)
    except httpx.HTTPError as exc:
        raise ScrapingError(f"Failed to download {doc.pdf_url}: {exc}") from exc

    return target


def discover_and_download(
    target_dir: Path,
    max_docs: int = 120,
    settings: Settings | None = None,
) -> Iterable[tuple[DiscoveredDocument, Path]]:
    """Discover RBI PDF links, download them, and yield (doc, path)."""
    docs = scrape_index_pages(max_docs=max_docs, settings=settings)
    for doc in docs:
        try:
            path = download_pdf(doc, target_dir, settings=settings)
        except ScrapingError as exc:
            logger.warning("Skipping %s: %s", doc.pdf_url, exc)
            continue
        yield doc, path


__all__ = [
    "DiscoveredDocument",
    "DiscoveredMasterDirection",
    "discover_and_download",
    "download_pdf",
    "rbi_url",
    "scrape_index_pages",
]
