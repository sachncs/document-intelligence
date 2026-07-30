"""PDF text extraction with vision-API fallback.

Strategy:
1. Try ``pypdf`` for cheap text extraction.
2. If a page yields < 50 chars (likely scanned), render it via pypdfium2
   and call the configured chat model vision API via LiteLLM.
3. Cache results by ``(pdf_sha256, page_number)`` to avoid double-billing.
"""

from __future__ import annotations

import hashlib
import io
import re
from pathlib import Path
from typing import Final

import pypdf
import pypdfium2 as pdfium  # type: ignore[import-untyped]
from litellm import completion
from pydantic import HttpUrl

from docendo.config import Settings, get_settings
from docendo.exceptions import PDFExtractionError, VisionAPIError
from docendo.logging import get_logger
from docendo.models import Page, Record

logger = get_logger(__name__)

_TEXT_PAGE_THRESHOLD: Final[int] = 50
_VISION_DPI: Final[int] = 200
_VISION_PROMPT: Final[str] = (
    "Extract all text from this document page, preserving structure "
    "(headings, paragraphs, list items, table cells). "
    "Return only the extracted text — no commentary, no markdown fencing."
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def render_page(pdf_path: Path, page_number: int, dpi: int = _VISION_DPI) -> bytes:
    """Render a 1-indexed PDF page to PNG bytes."""
    try:
        pdf = pdfium.PdfDocument(str(pdf_path))
    except Exception as exc:
        raise PDFExtractionError(f"Failed to open PDF {pdf_path}: {exc}") from exc

    if page_number < 1 or page_number > len(pdf):
        raise PDFExtractionError(
            f"Page {page_number} out of range (1..{len(pdf)}) for {pdf_path}"
        )

    page = pdf[page_number - 1]
    scale = dpi / 72.0
    bitmap = page.render(scale=scale)
    pil_image = bitmap.to_pil()
    buf = io.BytesIO()
    pil_image.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def read_page(png_bytes: bytes, settings: Settings | None = None) -> str:
    """Call the configured chat model's vision API to extract text from a rendered page."""
    settings = settings or get_settings()
    settings.require_llm()

    import base64

    b64 = base64.b64encode(png_bytes).decode("ascii")
    try:
        response = completion(
            model=settings.chat,
            api_key=settings.chat_key,
            api_base=settings.chat_url,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _VISION_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                    ],
                }
            ],
            max_tokens=4096,
            temperature=0.0,
        )
    except Exception as exc:
        raise VisionAPIError(f"Vision API call failed: {exc}") from exc

    try:
        content: str = response.choices[0].message.content
    except (AttributeError, IndexError, KeyError) as exc:
        raise VisionAPIError(f"Vision API returned malformed response: {exc}") from exc

    if not content or not content.strip():
        raise VisionAPIError("Vision API returned empty content")

    return content.strip()


def split_page(page: pypdf.PageObject) -> str:
    try:
        return page.extract_text() or ""
    except Exception:
        return ""


def parse_date(text: str) -> str | None:
    """Return ISO 8601 date if found in the first KB of text, else None."""
    head = text[:1500]
    patterns = [
        r"\b(\d{2})[/\-.](\d{2})[/\-.](\d{4})\b",
        r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})\b",
    ]
    for pat in patterns:
        m = re.search(pat, head)
        if not m:
            continue
        if pat.startswith(r"\b(\d{2}"):
            dd, mm, yyyy = m.groups()
            try:
                return f"{yyyy}-{int(mm):02d}-{int(dd):02d}"
            except ValueError:
                continue
        else:
            month_name, dd, yyyy = m.groups()
            months = {
                "January": 1,
                "February": 2,
                "March": 3,
                "April": 4,
                "May": 5,
                "June": 6,
                "July": 7,
                "August": 8,
                "September": 9,
                "October": 10,
                "November": 11,
                "December": 12,
            }
            try:
                return f"{yyyy}-{months[month_name]:02d}-{int(dd):02d}"
            except (KeyError, ValueError):
                continue
    return None


def read(
    pdf_path: Path,
    circular_id: str,
    title: str,
    source_url: str,
    topic: str = "general",
    settings: Settings | None = None,
) -> Record:
    """Extract a PDF, falling back to vision for scanned pages."""
    settings = settings or get_settings()
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise PDFExtractionError(f"PDF not found: {pdf_path}")

    logger.info("Reading %s (%s)", pdf_path.name, circular_id)

    try:
        reader = pypdf.PdfReader(str(pdf_path))
    except Exception as exc:
        raise PDFExtractionError(f"Failed to open PDF {pdf_path}: {exc}") from exc

    pages: list[Page] = []
    for i, page in enumerate(reader.pages, start=1):
        text = split_page(page).strip()
        if len(text) >= _TEXT_PAGE_THRESHOLD:
            pages.append(Page(page_number=i, text=text, method="text"))
            continue

        logger.info("Page %d of %s needs vision extraction", i, pdf_path.name)
        try:
            png = render_page(pdf_path, i)
            text = read_page(png, settings=settings)
            pages.append(Page(page_number=i, text=text, method="vision", confidence=0.85))
        except (VisionAPIError, PDFExtractionError) as exc:
            logger.warning("Vision extraction failed for page %d: %s", i, exc)
            pages.append(Page(page_number=i, text="", method="vision", confidence=0.0))

    full_text = "\n\n".join(p.text for p in pages if p.text)
    issue_date = parse_date(full_text)

    return Record(
        circular_id=circular_id,
        title=title,
        issue_date=issue_date,
        topic=topic,
        source_url=HttpUrl(source_url),
        pages=pages,
        full_text=full_text,
    )


__all__ = ["parse_date", "read", "read_page", "render_page", "sha256_file", "split_page"]
