from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

from pypdf import PdfReader

logger = logging.getLogger(__name__)


def parse_pdf(path: Path) -> Dict[str, Any]:
    reader = PdfReader(str(path))
    elements: List[Dict[str, Any]] = []

    for index, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:  # pragma: no cover - safety net
            logger.warning("Failed to extract text from page %s of %s: %s", index, path.name, exc)
            text = ""
        text = text.strip()
        if not text:
            text = "[No selectable text on this page – likely scanned or image-based.]"
        elements.append({"page_number": index, "text": text})

    if not elements:
        elements.append({"page_number": 1, "text": "[PDF contained no extractable pages.]"})

    payload: Dict[str, Any] = {
        "source_file": path.name,
        "page_count": len(elements),
        "elements": elements,
    }
    return payload


def pdf_yaml_summary(elements: List[Dict[str, Any]]) -> str:
    preview: List[str] = []
    for item in elements[:5]:
        text = (item.get("text") or "").strip()
        if text:
            preview.append(f"Page {item.get('page_number')}: {text[:200]}")
    return "\n".join(preview)
