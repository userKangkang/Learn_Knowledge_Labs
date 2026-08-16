"""Render PDF pages into compact image inputs for multimodal models."""

from __future__ import annotations

import base64
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def render_pdf_pages_as_data_urls(
    path: str | Path,
    *,
    max_pages: int,
    max_edge: int,
    jpeg_quality: int,
) -> tuple[list[tuple[int, str]], int]:
    """Render the first pages of a PDF as ``(page_number, data_url)`` pairs.

    The returned page number is one-based. Rendering is intentionally best-effort:
    text extraction remains usable if a PDF renderer is unavailable or a page
    cannot be rendered.
    """
    if max_pages <= 0 or max_edge <= 0:
        return [], 0

    try:
        import pymupdf
    except ImportError:
        logger.warning("PyMuPDF is not installed; PDF visual inputs are disabled")
        return [], 0

    document = None
    try:
        document = pymupdf.open(str(path))
        page_count = document.page_count
        page_limit = min(page_count, max_pages)
        quality = max(40, min(95, jpeg_quality))
        rendered: list[tuple[int, str]] = []

        for page_index in range(page_limit):
            page = document.load_page(page_index)
            rect = page.rect
            longest_side = max(float(rect.width), float(rect.height), 1.0)
            scale = max_edge / longest_side
            matrix = pymupdf.Matrix(scale, scale)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            encoded = base64.b64encode(pixmap.tobytes("jpeg", jpg_quality=quality)).decode("ascii")
            rendered.append((page_index + 1, f"data:image/jpeg;base64,{encoded}"))

        return rendered, page_count
    except Exception:  # noqa: BLE001
        logger.exception("Could not render PDF pages for visual analysis: %s", path)
        return [], 0
    finally:
        if document is not None:
            document.close()
