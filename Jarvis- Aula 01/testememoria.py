from __future__ import annotations

import json
import logging
from pathlib import Path

from dotenv import load_dotenv
from mem0 import MemoryClient


def _load_env_files() -> None:
    current_dir = Path(__file__).resolve().parent
    load_dotenv(current_dir / ".env")


_load_env_files()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class JarvisMemory:
    def __init__(self, user_name: str = "GabrielGoulartdeSouza"):
        self.user_name = user_name
        self.client = MemoryClient()

    def salvar_conversa(self) -> None:
        """Envia mensagens de teste para a memoria do Mem0."""
        print(f"\nEnviando novas memorias para: {self.user_name}...")

        messages = [
            {"role": "user", "content": "Ultimamente estou escutando muito Chris Grey."},
            {"role": "assistant", "content": "Otima escolha! Qual sua musica favorita dele?"},
            {
                "role": "user",
                "content": "Minha favorita e Let The World Burn e minha cor preferida e cinza.",
            },
        ]

        self.client.add(messages, user_id=self.user_name)
        print("Informacoes processadas e salvas com sucesso!")

    def buscar_memorias(self) -> list[dict[str, str | None]]:
        """Recupera as informacoes que o Jarvis aprendeu."""
        print(f"\nJarvis, o que voce lembra sobre {self.user_name}?")

        query = f"Quais sao as preferencias e gostos de {self.user_name}?"
        response = self.client.search(query, filters={"user_id": self.user_name})
        results = self._extrair_resultados(response)

        memories_list = []
        for item in results:
            if not isinstance(item, dict):
                continue

            memory = item.get("memory") or item.get("text") or item.get("content")
            if memory:
                updated_at = item.get("updated_at")
                memories_list.append(
                    {
                        "fato": str(memory),
                        "data": str(updated_at) if updated_at is not None else None,
                    }
                )

        return memories_list

    @staticmethod
    def _extrair_resultados(response: object) -> list[object]:
        if isinstance(response, dict):
            results = response.get("results", [])
        elif isinstance(response, list):
            results = response
        else:
            results = []

        return results if isinstance(results, list) else []


if __name__ == "__main__":
    brain = JarvisMemory("GabrielGoulartdeSouza")

    try:
        brain.salvar_conversa()
        historico = brain.buscar_memorias()
    except Exception as exc:
        logger.error("Erro ao testar memoria: %s", exc)
        raise SystemExit(1) from exc

    if historico:
        print(json.dumps(historico, indent=2, ensure_ascii=False))
    else:
        print("Nenhuma memoria encontrada para este usuario.")
