from __future__ import annotations

import threading
import time

_position = (0, 0)
_started = False
_lock = threading.Lock()


def _poll_mouse() -> None:
    global _position
    try:
        import pyautogui
    except Exception:
        return

    while True:
        try:
            pos = pyautogui.position()
            with _lock:
                _position = (int(pos.x), int(pos.y))
        except Exception:
            pass
        time.sleep(0.01)


def start_mouse_tracker() -> None:
    global _started
    if _started:
        return
    _started = True
    thread = threading.Thread(target=_poll_mouse, daemon=True)
    thread.start()


def get_live_position() -> tuple[int, int]:
    if not _started:
        start_mouse_tracker()
    with _lock:
        return _position

