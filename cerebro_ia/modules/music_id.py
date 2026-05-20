from __future__ import annotations

import asyncio


class MusicIdentifier:
    async def identify(self, seconds: int = 8, open_youtube: bool = True) -> str:
        try:
            from shazamio import Shazam
        except Exception as exc:
            return f"ShazamIO nao instalado/configurado: {exc}"

        try:
            import sounddevice as sd
            import soundfile as sf
        except Exception as exc:
            return f"Dependencias de captura de audio ausentes: {exc}"

        try:
            samplerate = 44100
            data = sd.rec(int(seconds * samplerate), samplerate=samplerate, channels=2)
            sd.wait()
            temp = "cache/music_capture.wav"
            sf.write(temp, data, samplerate)
            result = await Shazam().recognize(temp)
            track = result.get("track") or {}
            title = track.get("title", "desconhecida")
            subtitle = track.get("subtitle", "")
            return f"Musica identificada: {title} - {subtitle}".strip()
        except Exception as exc:
            return f"Erro ao identificar musica: {exc}"

