from __future__ import annotations

import json
from pathlib import Path

from core.config import CACHE_DIR


class PathMemory:
    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root else CACHE_DIR
        self.path = CACHE_DIR / "path_memory.json"
        self.data = {"apps": {}, "processes": {}}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self.data.update(json.loads(self.path.read_text(encoding="utf-8")))
            except Exception:
                self.data = {"apps": {}, "processes": {}}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _key(self, name: str) -> str:
        return " ".join(str(name).lower().strip().split())

    def get_app_path(self, name: str) -> str | None:
        return self.data.get("apps", {}).get(self._key(name))

    def set_app_path(self, name: str, path: str) -> None:
        self.data.setdefault("apps", {})[self._key(name)] = path
        self._save()

    def get_process_name(self, name: str) -> str | None:
        return self.data.get("processes", {}).get(self._key(name))

    def set_process_name(self, name: str, process_name: str) -> None:
        self.data.setdefault("processes", {})[self._key(name)] = process_name
        self._save()

    def list_saved(self) -> str:
        apps = self.data.get("apps", {})
        processes = self.data.get("processes", {})
        if not apps and not processes:
            return "Nenhum caminho ou processo salvo ainda."
        lines = ["Caminhos salvos:"]
        lines.extend(f"- app {key}: {value}" for key, value in sorted(apps.items()))
        lines.extend(f"- processo {key}: {value}" for key, value in sorted(processes.items()))
        return "\n".join(lines)

