from __future__ import annotations

import subprocess
from pathlib import Path


class GitProactiveService:
    def __init__(self, repo: Path):
        self.repo = Path(repo)

    def suggest_commit(self) -> str:
        status = subprocess.run(["git", "status", "--short"], cwd=self.repo, capture_output=True, text=True)
        if status.returncode != 0:
            return "Este diretorio nao parece ser um repositorio Git valido."
        lines = [line for line in status.stdout.splitlines() if line.strip()]
        if not lines:
            return "Nada para commitar."
        scope = "jarvis"
        if any("whatsapp" in line.lower() for line in lines):
            scope = "whatsapp"
        elif any("interface_web" in line.lower() for line in lines):
            scope = "ui"
        return f"feat({scope}): atualiza ecossistema Jarvis"

    def commit(self, message: str, confirmar: bool = False) -> str:
        if not confirmar:
            return f"Confirmacao necessaria para commit: {message}"
        subprocess.run(["git", "add", "-A"], cwd=self.repo, check=True)
        result = subprocess.run(["git", "commit", "-m", message], cwd=self.repo, capture_output=True, text=True)
        if result.returncode != 0:
            return f"Falha ao commitar: {result.stderr.strip()}"
        return result.stdout.strip()

