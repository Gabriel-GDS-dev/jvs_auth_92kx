from __future__ import annotations

from pathlib import Path

from core.config import CACHE_DIR


class CodeStyleMirror:
    def learn(self, root: str) -> str:
        base = Path(root).expanduser()
        if not base.exists():
            return f"Diretorio nao encontrado: {base}"
        files = list(base.rglob("*.py"))[:40] + list(base.rglob("*.ts"))[:40] + list(base.rglob("*.tsx"))[:40]
        indent_spaces = 0
        tabs = 0
        samples = 0
        for file in files:
            try:
                for line in file.read_text(encoding="utf-8", errors="ignore").splitlines():
                    if line.startswith("    "):
                        indent_spaces += 1
                    if line.startswith("\t"):
                        tabs += 1
                    samples += 1
            except Exception:
                continue
        style = "spaces" if indent_spaces >= tabs else "tabs"
        target = CACHE_DIR / "code_style_guide.txt"
        target.write_text(f"indentation={style}\nsamples={samples}\n", encoding="utf-8")
        return f"Guia de estilo salvo em {target}: indentacao por {style}."

