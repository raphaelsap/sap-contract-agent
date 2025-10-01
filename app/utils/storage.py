from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Dict

import yaml


class StorageManager:
    def __init__(self, data_root: Path, artefact_root: Path) -> None:
        self.data_root = data_root
        self.artefact_root = artefact_root
        self.data_root.mkdir(parents=True, exist_ok=True)
        self.artefact_root.mkdir(parents=True, exist_ok=True)

    def create_run_id(self) -> str:
        return uuid.uuid4().hex

    def _run_data_dir(self, run_id: str) -> Path:
        path = self.data_root / run_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _run_artefact_dir(self, run_id: str) -> Path:
        path = self.artefact_root / run_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_yaml(self, run_id: str, name: str, payload: Dict[str, Any]) -> Path:
        target = self._run_data_dir(run_id) / f"{name}.yaml"
        with target.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(payload, handle, sort_keys=False, allow_unicode=False)
        return target

    def save_markdown(self, run_id: str, name: str, content: str) -> Path:
        target = self._run_data_dir(run_id) / f"{name}.md"
        target.write_text(content, encoding="utf-8")
        return target

    def save_text(self, run_id: str, name: str, content: str, *, suffix: str = ".txt") -> Path:
        target = self._run_data_dir(run_id) / f"{name}{suffix}"
        target.write_text(content, encoding="utf-8")
        return target

    def save_raw_file(self, run_id: str, original_name: str, content: bytes) -> Path:
        target = self._run_artefact_dir(run_id) / original_name
        target.write_bytes(content)
        return target

    def load_yaml(self, path: Path) -> Dict[str, Any]:
        with path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle)

    def list_run_directories(self) -> Dict[str, Dict[str, Path]]:
        listing: Dict[str, Dict[str, Path]] = {}
        for run_dir in self.data_root.glob("*"):
            if run_dir.is_dir():
                listing[run_dir.name] = {
                    "data": run_dir,
                    "artefacts": self.artefact_root / run_dir.name,
                }
        return listing
