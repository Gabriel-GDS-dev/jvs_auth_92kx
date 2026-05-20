from __future__ import annotations

import difflib
import json
import unicodedata
from pathlib import Path

from core.config import CACHE_DIR, LOGS_DIR


class WhatsAppContactResolver:
    def __init__(self, cache_path: Path | None = None):
        self.cache_path = cache_path or CACHE_DIR / "whatsapp_contacts_cache.json"
        self.log_path = LOGS_DIR / "whatsapp_resolver.log"
        self.contacts: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if self.cache_path.exists():
            try:
                self.contacts = json.loads(self.cache_path.read_text(encoding="utf-8"))
            except Exception:
                self.contacts = {}

    def _save(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps(self.contacts, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def normalize(self, text: str) -> str:
        text = unicodedata.normalize("NFD", text.lower())
        text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
        for filler in ("mano", "pro", "pra", "para", "o", "a"):
            text = text.replace(f" {filler} ", " ")
        return " ".join(text.split())

    def learn(self, alias: str, contact: dict) -> None:
        key = self.normalize(alias)
        self.contacts[key] = contact
        self._save()

    def resolve(self, name: str, remote_contacts: list[dict] | None = None) -> dict:
        normalized = self.normalize(name)
        candidates = dict(self.contacts)
        for contact in remote_contacts or []:
            labels = [
                contact.get("name", ""),
                contact.get("pushname", ""),
                contact.get("number", ""),
                contact.get("id", ""),
            ]
            for label in labels:
                if label:
                    candidates[self.normalize(str(label))] = contact

        best_key = ""
        best_score = 0.0
        for key in candidates:
            score = difflib.SequenceMatcher(None, normalized, key).ratio()
            if normalized in key or key in normalized:
                score += 0.2
            if score > best_score:
                best_key = key
                best_score = score

        if not best_key:
            return {"found": False, "confidence": 0.0, "contact": None}

        contact = candidates[best_key]
        if best_score >= 0.78:
            self.learn(name, contact)
        return {"found": best_score >= 0.62, "confidence": round(best_score, 3), "contact": contact}

