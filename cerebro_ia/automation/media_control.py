from __future__ import annotations

import asyncio
import json
import urllib.request


class MediaControl:
    def __init__(self, cdp_url: str = "http://localhost:9222"):
        self.cdp_url = cdp_url.rstrip("/")

    def _media_key(self, key: str) -> str:
        try:
            import pyautogui

            pyautogui.press(key)
            return f"Tecla de midia '{key}' enviada."
        except Exception as exc:
            return f"Erro ao enviar tecla de midia: {exc}"

    async def control(self, action: str, value: str = "") -> str:
        action = action.lower().strip()
        if action in {"play", "pause", "toggle", "pausar", "retomar"}:
            return await self._control_html5("toggle")
        if action in {"next", "proxima", "proximo"}:
            return self._media_key("nexttrack")
        if action in {"previous", "anterior"}:
            return self._media_key("prevtrack")
        if action in {"volume_up", "aumentar_volume"}:
            return self._media_key("volumeup")
        if action in {"volume_down", "diminuir_volume"}:
            return self._media_key("volumedown")
        if action in {"seek", "avancar", "retroceder"}:
            return await self._control_html5(action, value)
        if action in {"speed", "velocidade"}:
            return await self._control_html5("speed", value)
        return f"Acao de midia desconhecida: {action}"

    async def _control_html5(self, action: str, value: str = "") -> str:
        try:
            from playwright.async_api import async_playwright
        except Exception:
            return "Playwright nao instalado; usando teclas globais quando possivel."

        try:
            with urllib.request.urlopen(f"{self.cdp_url}/json/version", timeout=1):
                pass
        except Exception:
            if action == "toggle":
                return self._media_key("playpause")
            return "CDP do navegador nao esta disponivel na porta 9222."

        script = """
        ([action, value]) => {
          const video = document.querySelector('video, audio');
          if (!video) return 'Nenhuma midia HTML5 encontrada.';
          if (action === 'toggle') { video.paused ? video.play() : video.pause(); return video.paused ? 'Pausado.' : 'Reproduzindo.'; }
          if (action === 'avancar' || action === 'seek') { video.currentTime += Number(value || 10); return 'Avancado.'; }
          if (action === 'retroceder') { video.currentTime = Math.max(0, video.currentTime - Number(value || 10)); return 'Retrocedido.'; }
          if (action === 'speed') { video.playbackRate = Number(value || 1); return 'Velocidade ajustada.'; }
          return 'Acao nao suportada.';
        }
        """
        try:
            async with async_playwright() as p:
                browser = await p.chromium.connect_over_cdp(self.cdp_url)
                for ctx in browser.contexts:
                    for page in ctx.pages:
                        if any(host in page.url for host in ("youtube", "netflix", "spotify", "music")):
                            result = await page.evaluate(script, [action, value])
                            await browser.disconnect()
                            return str(result)
                await browser.disconnect()
        except Exception as exc:
            return f"Erro ao controlar midia via CDP: {exc}"
        return "Nenhum player ativo encontrado no navegador."

