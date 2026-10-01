"""
tts.py -- Text-to-speech output using pyttsx3.

Public API
----------
speak(text: str) -> None
    Queues *text* for speech and returns immediately.
    Closes the thinking orb when voice response starts playing.
    Audio plays in a background daemon thread so it never blocks the pipeline.
"""

from __future__ import annotations

import threading

import pyttsx3

from clicky.config import get_tts_settings


# ---------------------------------------------------------------------------
# Engine -- initialised once at import time and reused across calls.
# Creating a new engine per call leaks OS audio resources on Windows.
# ---------------------------------------------------------------------------

_engine: pyttsx3.Engine = pyttsx3.init()
_tts_lock = threading.Lock()   # prevent two speak() calls overlapping


def _apply_settings() -> None:
    cfg = get_tts_settings()
    _engine.setProperty("rate",   cfg["rate"])
    _engine.setProperty("volume", cfg["volume"])

_apply_settings()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def speak(text: str) -> None:
    """Start speaking *text* and return immediately (non-blocking).

    Closes the thinking orb overlay when speech starts.
    The audio plays in a daemon thread so the pipeline lock is released
    as soon as this function returns.

    Parameters
    ----------
    text:
        The string to be spoken.  Empty / whitespace-only strings are
        silently ignored.
    """
    if not text or not text.strip():
        return

    # In tts.py, when voice response starts playing, close orb cleanly
    try:
        from orb_integration import get_orb_manager
        get_orb_manager().close_overlay()
    except Exception:
        pass

    def _run() -> None:
        with _tts_lock:
            try:
                # Ensure orb is closed immediately before speech plays
                try:
                    from orb_integration import get_orb_manager
                    get_orb_manager().close_overlay()
                except Exception:
                    pass

                _engine.say(text)
                _engine.runAndWait()
            except Exception as exc:
                print(f"[Clicky] TTS error: {exc}", flush=True)

    # Fire-and-forget -- do NOT join or wait on this thread.
    threading.Thread(target=_run, daemon=True, name="clicky-tts").start()
