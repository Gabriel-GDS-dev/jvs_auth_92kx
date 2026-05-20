from __future__ import annotations

import os
from dataclasses import dataclass

import requests

from core.config import require_env


@dataclass
class ProviderResponse:
    provider: str
    content: str


class MultiAIProviderManager:
    def require_keys_report(self) -> str:
        keys = [
            "GROQ_API_KEY",
            "OPENROUTER_API_KEY",
            "TAVILY_API_KEY",
            "SERPER_API_KEY",
            "JINA_API_KEY",
            "COHERE_API_KEY",
            "CARTESIA_API_KEY",
            "OCRSPACE_API_KEY",
        ]
        missing = [key for key in keys if not os.getenv(key)]
        if missing:
            return "Chaves ausentes: " + ", ".join(missing)
        return "Todas as chaves multi-IA esperadas estao configuradas."

    def openrouter_code(self, prompt: str, model: str = "deepseek/deepseek-r1") -> ProviderResponse:
        key = require_env("OPENROUTER_API_KEY", "OpenRouter Coder Specialist")
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": model, "messages": [{"role": "user", "content": prompt}]},
            timeout=45,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return ProviderResponse("openrouter", content)

    def groq_fast(self, prompt: str, model: str = "llama-3.1-8b-instant") -> ProviderResponse:
        key = require_env("GROQ_API_KEY", "Groq Fast Path")
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": model, "messages": [{"role": "user", "content": prompt}]},
            timeout=30,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return ProviderResponse("groq", content)

