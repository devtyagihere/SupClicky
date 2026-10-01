"""
config.py — Loads all Clicky settings.

Priority order:
  1. .env file in the project root  (secrets: GEMINI_API_KEY)
  2. config.yaml                    (behaviour: hotkey, prompt, model, tts)

The API key is never stored in config.yaml or anywhere else in the codebase.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# Project root = parent of this file's parent (clicky/config.py → root)
_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _ROOT / ".env"
_CONFIG_FILE = _ROOT / "config.yaml"

# ---------------------------------------------------------------------------
# Load .env  (must happen before anything reads os.environ)
# ---------------------------------------------------------------------------

load_dotenv(dotenv_path=_ENV_FILE)

# ---------------------------------------------------------------------------
# API key — sourced exclusively from the environment / .env file
# ---------------------------------------------------------------------------

def get_api_key() -> str:
    """Return the Gemini API key from the environment.

    Raises SystemExit with a clear message if the key is missing or still
    set to the placeholder value, so the tool fails fast rather than
    making an unauthenticated API call.
    """
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key or key == "your_api_key_here":
        sys.exit(
            "[Clicky] GEMINI_API_KEY is not set.\n"
            f"Open '{_ENV_FILE}' and replace 'your_api_key_here' with your "
            "actual Gemini API key, then restart Clicky."
        )
    return key

# ---------------------------------------------------------------------------
# Behaviour settings — loaded from config.yaml
# ---------------------------------------------------------------------------

def _load_yaml() -> dict:
    """Parse config.yaml and return its contents as a dict."""
    if not _CONFIG_FILE.exists():
        sys.exit(
            f"[Clicky] config.yaml not found at '{_CONFIG_FILE}'.\n"
            "Restore the file or re-clone the repository."
        )
    with _CONFIG_FILE.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


_cfg: dict = _load_yaml()

# Public accessors — callers import these rather than reading _cfg directly.

def get_hotkey() -> str:
    """Return the global hotkey string, e.g. '<ctrl>+<f1>'."""
    return str(_cfg.get("hotkey", "<ctrl>+<f1>"))


def get_quit_hotkey() -> str:
    """Return the quit hotkey string, e.g. '<alt>+<f1>'."""
    return str(_cfg.get("quit_hotkey", "<alt>+<f1>"))


def get_prompt() -> str:
    """Return the prompt that is sent to Gemini alongside the screenshot."""
    return str(_cfg.get("prompt", "What do you see in this screenshot? Summarize it concisely."))


def get_model() -> str:
    """Return the Gemini model name to use."""
    return str(_cfg.get("model", "gemini-3.8-flash"))


def get_tts_settings() -> dict:
    """Return TTS settings as a dict with keys 'rate' and 'volume'."""
    tts = _cfg.get("tts", {})
    return {
        "rate": int(tts.get("rate", 175)),
        "volume": float(tts.get("volume", 1.0)),
    }


def get_listen_timeout() -> int:
    """Return the microphone listen timeout in seconds."""
    return int(_cfg.get("listen_timeout", 3))


def get_annotation_duration() -> int:
    """Return how long (seconds) screen annotations stay visible before fading."""
    return int(_cfg.get("annotation_duration", 5))
