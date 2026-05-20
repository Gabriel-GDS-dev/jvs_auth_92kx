from __future__ import annotations

from pathlib import Path

from core.config import require_env


class AudioRAGBriefingService:
    def generate(self, document_path: str) -> str:
        require_env("COHERE_API_KEY", "Audio RAG Briefing")
        require_env("CARTESIA_API_KEY", "Audio RAG Briefing")
        path = Path(document_path).expanduser()
        if not path.exists():
            return f"Documento nao encontrado: {path}"
        text = path.read_text(encoding="utf-8", errors="ignore")[:8000]
        summary = "Boletim executivo:\n" + "\n".join(text.splitlines()[:20])
        return summary + "\nCartesia TTS configurado para sintese quando a chamada de audio for ativada."

