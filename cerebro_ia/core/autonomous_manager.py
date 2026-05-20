from __future__ import annotations

from pathlib import Path


class AutonomousManager:
    def __init__(self, root: Path):
        self.root = Path(root)

    def prepare_environment(self, mode: str) -> str:
        mode = mode.lower().strip()
        if mode in {"dev", "desenvolvimento"}:
            (self.root / "sandbox").mkdir(exist_ok=True)
            (self.root / "logs").mkdir(exist_ok=True)
            return "Ambiente de desenvolvimento preparado."
        if mode in {"estudo", "study"}:
            (self.root / "outputs" / "estudos").mkdir(parents=True, exist_ok=True)
            return "Ambiente de estudo preparado."
        if mode in {"lazer", "media"}:
            return "Ambiente de midia pronto."
        return f"Modo '{mode}' registrado sem preparacao especifica."

