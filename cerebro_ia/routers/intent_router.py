from __future__ import annotations

import re


class IntentRouter:
    CONNECTORS = r"\b(?:e depois|depois|entao|então|e tambem|e também)\b"

    def split_compound_command(self, command: str) -> list[str]:
        parts = [part.strip(" ,.;") for part in re.split(self.CONNECTORS, command, flags=re.I)]
        return [part for part in parts if part]

    def route(self, command: str) -> dict[str, object]:
        parts = self.split_compound_command(command)
        return {
            "compound": len(parts) > 1,
            "commands": parts,
            "priority": "fast_path" if any("abre" in p.lower() for p in parts) else "standard",
        }

