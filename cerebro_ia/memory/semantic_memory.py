from __future__ import annotations

import json
from pathlib import Path

from core.config import CACHE_DIR


class SemanticMemory:
    def __init__(self, path: Path | None = None):
        self.path = path or CACHE_DIR / "semantic_memory.json"
        self.items: list[dict[str, str]] = []
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self.items = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self.items = []

    def _save(self) -> None:
        self.path.write_text(json.dumps(self.items, ensure_ascii=False, indent=2), encoding="utf-8")

    def add(self, text: str, namespace: str = "default") -> None:
        self.items.append({"namespace": namespace, "text": text})
        self.items = self.items[-500:]
        self._save()

    def search(self, query: str, limit: int = 5) -> list[str]:
        terms = set(query.lower().split())
        scored = []
        for item in self.items:
            score = len(terms.intersection(item["text"].lower().split()))
            if score:
                scored.append((score, item["text"]))
        scored.sort(reverse=True)
        return [text for _, text in scored[:limit]]

