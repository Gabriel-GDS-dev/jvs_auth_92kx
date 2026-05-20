from __future__ import annotations

from datetime import datetime


class MeetingGhostScribe:
    MEETING_HINTS = ("zoom", "teams", "meet", "discord")

    def detect_meeting(self) -> bool:
        try:
            import pygetwindow as gw

            titles = " ".join(w.title.lower() for w in gw.getAllWindows())
            return any(hint in titles for hint in self.MEETING_HINTS)
        except Exception:
            return False

    def draft_minutes(self) -> str:
        status = "detectada" if self.detect_meeting() else "nao detectada"
        return (
            f"# Ata Executiva - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            f"Status da reuniao: {status}.\n\n"
            "## Resumo\n- Aguardando transcricao ou notas da reuniao.\n\n"
            "## Decisoes\n- Nenhuma decisao registrada automaticamente.\n\n"
            "## Prazos\n- Nenhum prazo registrado automaticamente.\n"
        )

