from __future__ import annotations


class EmotionalAnalyzer:
    def analyze(self, text: str) -> dict[str, str | int]:
        normalized = text.lower()
        urgency = 1
        mood = "Neutral"
        if any(word in normalized for word in ("urgente", "rapido", "agora", "correndo")):
            urgency = 8
            mood = "Rushed"
        if any(word in normalized for word in ("erro", "falha", "travou", "raiva", "estresse")):
            urgency = max(urgency, 7)
            mood = "Stressed"
        return {"mood": mood, "urgency": urgency}

