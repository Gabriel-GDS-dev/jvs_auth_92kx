from __future__ import annotations

from core.emotional import EmotionalAnalyzer


class ProactiveEngine:
    def __init__(self):
        self.emotions = EmotionalAnalyzer()

    def evaluate_task(self, text: str) -> dict[str, str | int | list[str]]:
        emotion = self.emotions.analyze(text)
        suggestions: list[str] = []
        if emotion["urgency"] >= 7:
            suggestions.append("priorizar execucao antes da resposta")
        if "erro" in text.lower():
            suggestions.append("coletar logs e propor correcao")
        return {
            "priority": emotion["urgency"],
            "mood": emotion["mood"],
            "suggestions": suggestions,
        }

