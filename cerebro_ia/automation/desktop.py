from __future__ import annotations

import ctypes
import difflib
import os
import re
import subprocess
import time
from pathlib import Path

from automation.mouse_tracker import get_live_position
from modules.path_memory import PathMemory


class DesktopAutomation:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.path_memory = PathMemory(self.root)

    def click_live_cursor(self) -> str:
        x, y = get_live_position()
        return self.click(x, y)

    def click(self, x: int, y: int) -> str:
        try:
            import pyautogui

            if x <= 1 and y <= 1:
                return "Failsafe acionado: canto superior esquerdo bloqueado."
            pyautogui.click(int(x), int(y))
            return f"Clique executado em ({int(x)}, {int(y)})."
        except Exception as exc:
            return f"Erro ao clicar: {exc}"

    def spam_click(self, quantidade: int = 10, intervalo_ms: int = 20) -> str:
        quantidade = max(1, min(int(quantidade), 500))
        intervalo = max(0, int(intervalo_ms)) / 1000
        x, y = get_live_position()
        if x <= 1 and y <= 1:
            return "Failsafe acionado: canto superior esquerdo bloqueado."
        try:
            user32 = ctypes.windll.user32
            for _ in range(quantidade):
                user32.SetCursorPos(int(x), int(y))
                user32.mouse_event(0x0002, 0, 0, 0, 0)
                user32.mouse_event(0x0004, 0, 0, 0, 0)
                if intervalo:
                    time.sleep(intervalo)
            return f"Rajada de {quantidade} cliques executada em ({x}, {y})."
        except Exception:
            try:
                import pyautogui

                pyautogui.click(int(x), int(y), clicks=quantidade, interval=intervalo)
                return f"Rajada de {quantidade} cliques executada em ({x}, {y})."
            except Exception as exc:
                return f"Erro no spam_click: {exc}"

    def abrir_aplicativo_memorizado(self, nome: str) -> str:
        nome = nome.strip()
        saved = self.path_memory.get_app_path(nome)
        if saved and Path(saved).exists():
            subprocess.Popen([saved], shell=False)
            return f"Abrindo {nome} por caminho memorizado."

        found = self._find_executable(nome)
        if found:
            self.path_memory.set_app_path(nome, str(found))
            subprocess.Popen([str(found)], shell=False)
            return f"Abrindo {nome}; caminho memorizado em {found}."

        try:
            subprocess.Popen(["cmd", "/c", "start", "", nome], shell=False)
            return f"Tentando abrir {nome} pelo Windows."
        except Exception as exc:
            return f"Nao encontrei caminho local para {nome}: {exc}"

    def _find_executable(self, nome: str) -> Path | None:
        candidates = [
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
            Path(os.environ.get("LOCALAPPDATA", "")),
            Path(os.environ.get("APPDATA", "")),
        ]
        needle = re.sub(r"[^a-z0-9]+", "", nome.lower())
        best: tuple[float, Path] | None = None
        for base in candidates:
            if not base.exists():
                continue
            try:
                for path in base.rglob("*.exe"):
                    compact = re.sub(r"[^a-z0-9]+", "", path.stem.lower())
                    score = difflib.SequenceMatcher(None, needle, compact).ratio()
                    if needle in compact:
                        score += 0.2
                    if score >= 0.72 and (best is None or score > best[0]):
                        best = (score, path)
            except Exception:
                continue
        return best[1] if best else None

    def fechar_programa_inteligente(self, programa: str, confirmar: bool = False) -> str:
        if self._is_sensitive_process(programa) and not confirmar:
            return f"Confirmacao necessaria para fechar '{programa}'. Chame novamente com confirmar=True."

        cached = self.path_memory.get_process_name(programa)
        if cached:
            result = subprocess.run(["taskkill", "/f", "/im", cached], capture_output=True, text=True)
            if result.returncode == 0:
                return f"Programa '{programa}' fechado via processo memorizado ({cached})."

        match = self._find_running_process(programa)
        if match:
            self.path_memory.set_process_name(programa, match)
            result = subprocess.run(["taskkill", "/f", "/im", match], capture_output=True, text=True)
            if result.returncode == 0:
                return f"Programa '{programa}' fechado via processo detectado ({match})."

        exe = programa if programa.lower().endswith(".exe") else f"{programa}.exe"
        result = subprocess.run(["taskkill", "/f", "/im", exe], capture_output=True, text=True)
        if result.returncode == 0:
            self.path_memory.set_process_name(programa, exe)
            return f"Programa '{programa}' fechado pelo fallback taskkill."
        return f"Nao foi possivel fechar '{programa}'. Processo nao encontrado localmente."

    def _find_running_process(self, programa: str) -> str | None:
        try:
            import psutil
        except Exception:
            return None
        needle = programa.lower().replace(".exe", "")
        best: tuple[float, str] | None = None
        for proc in psutil.process_iter(["name"]):
            name = (proc.info.get("name") or "").strip()
            if not name:
                continue
            compact = name.lower().replace(".exe", "")
            score = difflib.SequenceMatcher(None, needle, compact).ratio()
            if needle in compact or compact in needle:
                score += 0.25
            if score >= 0.65 and (best is None or score > best[0]):
                best = (score, name)
        return best[1] if best else None

    def _is_sensitive_process(self, programa: str) -> bool:
        normalized = programa.lower()
        return any(word in normalized for word in ("explorer", "code", "cursor", "python", "node", "chrome"))

