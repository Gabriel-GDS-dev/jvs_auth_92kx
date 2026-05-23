from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from modules.path_memory import PathMemory
from modules.smart_writer import SmartTextAutomation
from routers.intent_router import IntentRouter
from services.spotify_service import SpotifyService


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

    def test_spotify_url_to_uri(self):
        self.assertEqual(
            SpotifyService.spotify_uri_from_input("https://open.spotify.com/track/abc123?si=teste"),
            ("track", "spotify:track:abc123"),
        )
        self.assertEqual(
            SpotifyService.spotify_uri_from_input("spotify:playlist:xyz789"),
            ("playlist", "spotify:playlist:xyz789"),
        )


if __name__ == "__main__":
    unittest.main()
