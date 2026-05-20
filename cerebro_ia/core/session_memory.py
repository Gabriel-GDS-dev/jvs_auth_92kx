from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from core.config import CACHE_DIR


@dataclass
class SessionState:
    active_project: str = ""
    last_topic: str = ""
    focus_mode: str = "normal"
    mood: str = "neutral"
    coding_minutes: int = 0
    error_history: list[str] = field(default_factory=list)
    conversation_notes: list[str] = field(default_factory=list)
    updated_at: str = ""


class SessionMemory:
    _instance: "SessionMemory | None" = None

    def __new__(cls, path: Path | None = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, path: Path | None = None):
        if self._initialized:
            return
        self.path = path or CACHE_DIR / "session_state.json"
        self.state = SessionState()
        self._load_from_disk()
        self._initialized = True

    def _touch(self) -> None:
        self.state.updated_at = datetime.now().isoformat(timespec="seconds")

    def _load_from_disk(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.state = SessionState(**{**asdict(SessionState()), **data})
        except Exception:
            self.state = SessionState()

    def _save_to_disk(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._touch()
        self.path.write_text(
            json.dumps(asdict(self.state), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def update(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            if hasattr(self.state, key):
                setattr(self.state, key, value)
        self._save_to_disk()

    def remember_conversation(self, note: str) -> None:
        note = str(note).strip()
        if not note:
            return
        self.state.conversation_notes = (self.state.conversation_notes + [note])[-20:]
        self._save_to_disk()

    def add_error(self, error: str) -> None:
        error = str(error).strip()
        if not error:
            return
        self.state.error_history = (self.state.error_history + [error])[-20:]
        self._save_to_disk()

    def summary(self) -> str:
        parts = []
        if self.state.active_project:
            parts.append(f"Projeto ativo anterior: {self.state.active_project}")
        if self.state.last_topic:
            parts.append(f"Ultimo topico: {self.state.last_topic}")
        if self.state.focus_mode:
            parts.append(f"Modo de foco: {self.state.focus_mode}")
        if self.state.mood:
            parts.append(f"Humor percebido: {self.state.mood}")
        if self.state.conversation_notes:
            parts.append("Notas recentes: " + " | ".join(self.state.conversation_notes[-5:]))
        return "\n".join(parts)

