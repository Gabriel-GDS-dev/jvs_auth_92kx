from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from core.config import SANDBOX_DIR
from providers.multi_ai_providers import MultiAIProviderManager


class SandboxDevAgent:
    def __init__(self):
        self.providers = MultiAIProviderManager()

    def run_python(self, code: str, filename: str = "task.py") -> str:
        SANDBOX_DIR.mkdir(parents=True, exist_ok=True)
        path = SANDBOX_DIR / filename
        path.write_text(code, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(path)],
            capture_output=True,
            text=True,
            timeout=20,
            cwd=str(SANDBOX_DIR),
        )
        if result.returncode == 0:
            return result.stdout.strip() or "Codigo executado sem saida."
        return f"Codigo falhou ({result.returncode}):\n{result.stderr.strip()}"
