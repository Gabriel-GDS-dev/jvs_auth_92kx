from __future__ import annotations

from dataclasses import asdict

from vision.streaming import get_latest_vision


class OmniParserVision:
    def parse_screen(self) -> str:
        title = self._active_window_title()
        vision = get_latest_vision()
        ocr = self._ocr_screen()
        return (
            f"Janela ativa: {title}\n"
            f"Visao em tempo real: {asdict(vision)}\n"
            f"Texto visivel via OCR:\n{ocr}"
        )

    def find_element_coordinates(self, text: str) -> dict[str, int | str | bool]:
        try:
            import pyautogui
            import pytesseract

            image = pyautogui.screenshot()
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
            needle = text.lower().strip()
            best = None
            for i, word in enumerate(data.get("text", [])):
                if needle and needle in str(word).lower():
                    x = int(data["left"][i] + data["width"][i] / 2)
                    y = int(data["top"][i] + data["height"][i] / 2)
                    best = {"found": True, "x": x, "y": y, "text": word}
                    break
            return best or {"found": False, "text": text}
        except Exception as exc:
            return {"found": False, "text": text, "error": str(exc)}

    def _active_window_title(self) -> str:
        try:
            import pygetwindow as gw

            window = gw.getActiveWindow()
            return window.title if window else "(sem janela ativa)"
        except Exception:
            return "(titulo indisponivel)"

    def _ocr_screen(self) -> str:
        try:
            import pyautogui
            import pytesseract

            image = pyautogui.screenshot()
            return pytesseract.image_to_string(image, lang="por+eng").strip()[:4000]
        except Exception as exc:
            return f"OCR indisponivel: {exc}"

