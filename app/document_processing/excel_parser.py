from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd


def _to_builtin(value):
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {k: _to_builtin(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_builtin(v) for v in value]
    return value

def parse_excel(path: Path) -> Dict[str, Any]:
    workbook = pd.read_excel(path, sheet_name=None)
    output: Dict[str, Any] = {"source_file": path.name, "sheets": {}}
    for sheet_name, frame in workbook.items():
        frame = frame.fillna("")
        rows = _to_builtin(frame.to_dict(orient="records"))
        output["sheets"][sheet_name] = {
            "row_count": len(frame.index),
            "columns": list(frame.columns),
            "rows": rows,
        }
    return output
