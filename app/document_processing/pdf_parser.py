from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from unstructured.partition.pdf import partition_pdf




def _to_builtin(value):
    import numpy as np
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {k: _to_builtin(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_builtin(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_to_builtin(v) for v in value)
    return value

def parse_pdf(path: Path) -> Dict[str, Any]:
    try:
        elements = partition_pdf(
            filename=str(path),
            strategy="hi_res",
            infer_table_structure=True,
        )
    except Exception as exc:
        hint = ("Install Poppler and Tesseract and ensure they are available on the PATH. Original error: ")
        raise RuntimeError(hint + str(exc)) from exc
    payload: Dict[str, Any] = {
        "source_file": path.name,
        "element_count": len(elements),
        "elements": [_to_builtin(element.to_dict()) for element in elements],
    }
    return _to_builtin(payload)


def pdf_yaml_summary(elements: List[Dict[str, Any]]) -> str:
    preview: List[str] = []
    for item in elements[:10]:
        text = item.get("text", "").strip()
        if text:
            preview.append(text)
    return "\n".join(preview)
