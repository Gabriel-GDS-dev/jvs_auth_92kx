from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from modules.path_memory import PathMemory
from modules.smart_writer import SmartTextAutomation
from routers.intent_router import IntentRouter


class CoreModuleTests(unittest.TestCase):
    def test_intent_router_splits_compound_commands(self):
        router = IntentRouter()
        self.assertEqual(
            router.split_compound_command("abre o spotify e depois manda oi"),
            ["abre o spotify", "manda oi"],
        )

    def test_path_memory_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = PathMemory(Path(tmp))
            memory.path = Path(tmp) / "path_memory.json"
            memory.set_process_name("roblox", "RobloxPlayerBeta.exe")
            self.assertEqual(memory.get_process_name("Roblox"), "RobloxPlayerBeta.exe")

    def test_hotkey_parser_detects_hotkeys(self):
        writer = SmartTextAutomation()
        self.assertFalse(writer.parse_and_execute_keys("texto normal"))


if __name__ == "__main__":
    unittest.main()

