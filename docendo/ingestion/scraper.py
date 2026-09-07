"""Public-site scraper.

Fetches the index pages, extracts downloadable PDF links, and downloads
the files. The site is plain HTML tables - no JS, no auth.
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

BASE = "https://www.rbi.org.in"

MASTER_DIRECTIONS_INDEX = "https://website.rbi.org.in/web-rules/notifications/master-directions"
MASTER_CIRCULARS_INDEX = "https://website.rbi.org.in/web-rules/notifications/master-circulars"
NOTIFICATIONS_INDEX = "https://www.rbi.org.in/Scripts/NotificationUser.aspx"


@dataclass(frozen=True)
class Found:
    """A PDF document discovered on the index pages."""

    circular_id: str  # derived from title or URL slug
    title: str
    pdf_url: str
    source_page: str
    topic: str  # "master_direction" | "master_circular" | "circular"


@dataclass(frozen=True)
class Direction:
    """A master direction index entry (may have one or more PDFs)."""

    title: str
    detail_url: str
    pdf_url: str | None
    topic: str


def url(path: str) -> str:
    """Build an absolute RBI URL from a relative path."""
    return urljoin(BASE + "/", path.lstrip("/"))


def http_get(target_url: str, settings: Settings) -> str:
    """Fetch a URL with retry, return text content."""
    headers = {
        "User-Agent": "docendo/0.3 (+research; not for production compliance)",
        "Accept": "text/html,application/pdf",
    }
    try:
        with httpx.Client(
            timeout=settings.http_timeout,
            headers=headers,
            follow_redirects=True,
        ) as client:
            r = client.get(target_url)
            r.raise_for_status()
            return r.text
    except httpx.HTTPError as exc:
        raise ScrapingError(f"GET {target_url} failed: {exc}") from exc


def slugify(title: str, target_url: str) -> str:
    """Derive a deterministic circular ID from a title or URL."""
    slug = re.sub(r"[^A-Za-z0-9]+", "-", title or target_url).strip("-")[:80]
    return slug or "rbi-doc"


def parse_links(
    html: str, base_url: str, topic: str, max_docs: int
) -> list[Found]:
    """Parse a table of notification links and return PDF entries."""
    soup = BeautifulSoup(html, "html.parser")
    results: list[Found] = []
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if ".pdf" not in href.lower():
            continue
        title = link.get_text(strip=True) or href
        pdf_url = urljoin(base_url, href)
        if not pdf_url.startswith(("http://", "https://")):
            continue
        results.append(
            Found(
                circular_id=slugify(title, pdf_url),
                title=title,
                pdf_url=pdf_url,
                source_page=base_url,
                topic=topic,
            )
        )
        if len(results) >= max_docs:
            break
    return results


def scrape(max_docs: int = 120, settings: Settings | None = None) -> list[Found]:
    """Scrape notification index pages and return up to ``max_docs`` PDFs."""
    settings = settings or get_settings()
    logger.info("Scraping index pages (max_docs=%d)", max_docs)
    docs: list[Found] = []

    for target_url, topic in (
        (MASTER_DIRECTIONS_INDEX, "master_direction"),
        (MASTER_CIRCULARS_INDEX, "master_circular"),
        (NOTIFICATIONS_INDEX, "circular"),
    ):
        if len(docs) >= max_docs:
            break
        try:
            html = http_get(target_url, settings)
        except ScrapingError as exc:
            logger.warning("Skipping %s: %s", target_url, exc)
            continue
        new_docs = parse_links(html, target_url, topic, max_docs - len(docs))
        docs.extend(new_docs)
        logger.info("Found %d PDFs at %s", len(new_docs), target_url)

    seen: set[str] = set()
    unique: list[Found] = []
    for d in docs:
        if d.pdf_url in seen:
            continue
        seen.add(d.pdf_url)
        unique.append(d)
    return unique[:max_docs]


def download(
    doc: Found, target_dir: Path, settings: Settings | None = None
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
                timeout=settings.http_timeout,
                follow_redirects=True,
                headers={"User-Agent": "docendo/0.3"},
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


def discover(
    target_dir: Path,
    max_docs: int = 120,
    settings: Settings | None = None,
) -> Iterable[tuple[Found, Path]]:
    """Discover PDF links, download them, and yield (doc, path)."""
    docs = scrape(max_docs=max_docs, settings=settings)
    for doc in docs:
        try:
            path = download(doc, target_dir, settings=settings)
        except ScrapingError as exc:
            logger.warning("Skipping %s: %s", doc.pdf_url, exc)
            continue
        yield doc, path


__all__ = [
    "Direction",
    "Found",
    "discover",
    "download",
    "http_get",
    "parse_links",
    "scrape",
    "slugify",
    "url",
]
