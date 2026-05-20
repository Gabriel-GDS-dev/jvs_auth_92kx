from __future__ import annotations

import logging
import os
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
CACHE_DIR = PROJECT_DIR / "cache"
LOGS_DIR = PROJECT_DIR / "logs"
SANDBOX_DIR = PROJECT_DIR / "sandbox"

for _path in (CACHE_DIR, LOGS_DIR, SANDBOX_DIR):
    _path.mkdir(parents=True, exist_ok=True)


def setup_logging(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(LOGS_DIR / "jarvis_ecosystem.log", encoding="utf-8")
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "sim"}


def env_int(name: str, default: int, *, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def env_float(
    name: str,
    default: float,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError:
        value = default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def canonicalize_gemini_environment() -> str | None:
    """Use GEMINI_API_KEY as the only key visible to google-genai."""
    gemini_key = (os.getenv("GEMINI_API_KEY") or "").strip()
    google_key = (os.getenv("GOOGLE_API_KEY") or "").strip()

    if gemini_key:
        os.environ["GEMINI_API_KEY"] = gemini_key
        os.environ.pop("GOOGLE_API_KEY", None)
        return gemini_key

    if google_key:
        os.environ["GEMINI_API_KEY"] = google_key
        os.environ.pop("GOOGLE_API_KEY", None)
        return google_key

    return None


def require_env(name: str, service: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise RuntimeError(
            f"{service} exige a variavel {name}. Configure no .env antes de usar esta ferramenta."
        )
    return value

