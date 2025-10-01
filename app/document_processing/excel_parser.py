from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pandas as pd


def parse_excel(path: Path) -> Dict[str, Any]:
    workbook = pd.read_excel(path, sheet_name=None, dtype=str)
    output: Dict[str, Any] = {"source_file": path.name, "sheets": {}}
    for sheet_name, frame in workbook.items():
        frame = frame.fillna("")
        output["sheets"][sheet_name] = {
            "row_count": len(frame.index),
            "columns": list(frame.columns),
            "rows": frame.to_dict(orient="records"),
        }
    return output
