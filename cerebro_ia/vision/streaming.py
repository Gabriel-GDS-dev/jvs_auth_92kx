from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any

LATEST_FRAME: Any = None
LATEST_FRAME_AT = 0.0
_previous_frame: Any = None
_motion_score = 0.0
_started = False
_lock = threading.Lock()


@dataclass
class VisionState:
    has_frame: bool
    age_seconds: float
    motion_score: float
    fps_target: int


def _capture_loop(fps: int) -> None:
    global LATEST_FRAME, LATEST_FRAME_AT, _previous_frame, _motion_score
    delay = 1.0 / max(1, fps)
    try:
        import dxcam

        camera = dxcam.create(output_idx=0)
        camera.start(target_fps=fps)
        while True:
            frame = camera.get_latest_frame()
            if frame is not None:
                with _lock:
                    if _previous_frame is not None:
                        try:
                            diff = abs(frame.astype("int16") - _previous_frame.astype("int16")).mean()
                            _motion_score = float(diff)
                        except Exception:
                            _motion_score = 0.0
                    _previous_frame = frame
                    LATEST_FRAME = frame
                    LATEST_FRAME_AT = time.time()
            time.sleep(delay)
    except Exception:
        while True:
            time.sleep(delay)


def start_vision_stream(fps: int = 15) -> None:
    global _started
    if _started:
        return
    _started = True
    thread = threading.Thread(target=_capture_loop, args=(fps,), daemon=True)
    thread.start()


def get_latest_vision() -> VisionState:
    if not _started:
        start_vision_stream()
    with _lock:
        age = time.time() - LATEST_FRAME_AT if LATEST_FRAME_AT else 9999.0
        return VisionState(LATEST_FRAME is not None, age, _motion_score, 15)

