from __future__ import annotations

import re
import subprocess
import time


class SmartTextAutomation:
    KEY_MAP = {
        "CTRL": "ctrl",
        "ALT": "alt",
        "SHIFT": "shift",
        "ENTER": "enter",
        "BACKSPACE": "backspace",
        "DELETE": "delete",
        "TAB": "tab",
        "ESC": "esc",
        "SPACE": "space",
    }

    def parse_and_execute_keys(self, text: str) -> bool:
        if "{" not in text or "}" not in text:
            return False
        try:
            import pyautogui
        except Exception:
            return False

        tokens = re.findall(r"\{([^}]+)\}|([^{}]+)", text)
        pending_mods: list[str] = []
        executed = False
        for key_token, literal in tokens:
            if key_token:
                parts = [p.strip().upper() for p in re.split(r"[+ ]+", key_token) if p.strip()]
                mapped = [self.KEY_MAP.get(part, part.lower()) for part in parts]
                if len(mapped) == 1 and mapped[0] in {"ctrl", "alt", "shift"}:
                    pending_mods.append(mapped[0])
                elif len(mapped) > 1:
                    pyautogui.hotkey(*mapped)
                    executed = True
                else:
                    if pending_mods:
                        pyautogui.hotkey(*pending_mods, mapped[0])
                        pending_mods.clear()
                    else:
                        pyautogui.press(mapped[0])
                    executed = True
            elif literal.strip():
                for char in literal.strip():
                    if pending_mods:
                        pyautogui.hotkey(*pending_mods, char.lower())
                        pending_mods.clear()
                    else:
                        pyautogui.write(char)
                    executed = True
        return executed

    def execute_smart_writing(self, text: str, target_hint: str = "") -> str:
        if self.parse_and_execute_keys(text):
            return "Atalho executado."
        try:
            import pyautogui
        except Exception as exc:
            return f"pyautogui nao instalado: {exc}"

        try:
            if target_hint:
                self._focus_window(target_hint)
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value $args[0]", text],
                capture_output=True,
                text=True,
                timeout=5,
            )
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.2)
            return "Texto escrito no campo ativo."
        except Exception as exc:
            return f"Erro ao escrever texto: {exc}"

    def _focus_window(self, target_hint: str) -> None:
        try:
            import pygetwindow as gw

            for window in gw.getAllWindows():
                if target_hint.lower() in window.title.lower():
                    window.activate()
                    time.sleep(0.2)
                    return
        except Exception:
            return

