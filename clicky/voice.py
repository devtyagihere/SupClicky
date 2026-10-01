"""
voice.py -- Microphone input and speech-to-text transcription.

Public API
----------
listen() -> str
    Records audio from the default microphone for up to *listen_timeout*
    seconds (from config.yaml), transcribes it with Google Speech Recognition,
    and returns the spoken text.  Returns an empty string if nothing was heard
    or transcription fails, so callers can fall back to the default prompt.
"""

from __future__ import annotations

import speech_recognition as sr

from clicky.config import get_listen_timeout


def listen() -> str:
    """Record and transcribe speech from the microphone.

    Returns
    -------
    str
        Transcribed text, or an empty string if no speech was detected,
        the audio was unintelligible, or a network/microphone error occurred.
        The caller is responsible for deciding what to do with an empty result
        (e.g. fall back to the configured default prompt).
    """
    timeout = get_listen_timeout()
    recognizer = sr.Recognizer()

    try:
        with sr.Microphone() as source:
            # Briefly calibrate to ambient noise so the recogniser knows
            # what silence sounds like — makes detection more reliable.
            print("[Clicky] Calibrating microphone...", flush=True)
            recognizer.adjust_for_ambient_noise(source, duration=0.3)

            print(f"[Clicky] Listening for {timeout}s — speak your question now...", flush=True)
            audio = recognizer.listen(
                source,
                timeout=timeout,          # max seconds to wait for speech to start
                phrase_time_limit=timeout, # max seconds of speech to record
            )

    except sr.WaitTimeoutError:
        print("[Clicky] No speech detected within the timeout.", flush=True)
        return ""
    except OSError as exc:
        # Microphone not found or not accessible.
        print(f"[Clicky] Microphone error: {exc}", flush=True)
        return ""

    # Transcribe using Google's free web speech API (no key required).
    try:
        text = recognizer.recognize_google(audio).strip()
        return text
    except sr.UnknownValueError:
        print("[Clicky] Speech was not intelligible — could not transcribe.", flush=True)
        return ""
    except sr.RequestError as exc:
        print(f"[Clicky] Speech recognition service error: {exc}", flush=True)
        return ""
