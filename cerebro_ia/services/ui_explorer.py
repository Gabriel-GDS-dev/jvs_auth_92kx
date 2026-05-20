from __future__ import annotations

import json
from pathlib import Path

from core.config import CACHE_DIR
from vision.omniparser_vision import OmniParserVision


class AutonomousUIExplorer:
    def explore(self, app_name: str = "active") -> str:
        vision = OmniParserVision()
        summary = vision.parse_screen()
        target = CACHE_DIR / "ui_maps" / f"{app_name}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"app": app_name, "summary": summary}, ensure_ascii=False, indent=2), encoding="utf-8")
        return f"Mapa de interface salvo em {target}"

