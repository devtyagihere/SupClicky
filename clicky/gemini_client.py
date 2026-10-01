"""
gemini_client.py -- Sends a screenshot to the Gemini API and returns the response text.

Public API
----------
query(image_path, question=None) -> str
    Plain text response.

query_annotated(image_path, question=None) -> tuple[str, list[dict]]
    Returns (explanation_text, annotations_list).
    explanation_text -- spoken aloud by TTS.
    annotations_list -- passed to annotate.draw_annotations().
"""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

from clicky.config import get_api_key, get_model, get_prompt

# ---------------------------------------------------------------------------
# Timeouts
# ---------------------------------------------------------------------------

_TIMEOUT_SECONDS      = 60   # first attempt
_RETRY_TIMEOUT_SECONDS = 45  # one retry if first attempt times out

# ---------------------------------------------------------------------------
# Annotation system instruction (used as system_instruction in config,
# not as part of user content -- separating it gives more reliable JSON output)
# ---------------------------------------------------------------------------

_ANNOTATION_SYSTEM = (
    "Analyze the screenshot and respond with ONLY a valid JSON object "
    "(no markdown, no code fences, no text outside the JSON).\n"
    'Use this structure: {"explanation": "2-3 sentence spoken answer", '
    '"annotations": [...]}\n'
    "Annotation types (all coords normalized 0.0-1.0, top-left=(0,0), bottom-right=(1,1)):\n"
    '  rectangle: {"type":"rectangle","x1":0.1,"y1":0.1,"x2":0.5,"y2":0.5,"label":"name","color":"#FF4444"}\n'
    '  circle:    {"type":"circle","cx":0.5,"cy":0.5,"r":0.08,"label":"name","color":"#44FF44"}\n'
    '  arrow:     {"type":"arrow","x1":0.8,"y1":0.9,"x2":0.5,"y2":0.5,"label":"name","color":"#4488FF"}\n'
    '  text:      {"type":"text","x":0.1,"y":0.1,"label":"note","color":"#FFFF44"}\n'
    "Add 2-4 annotations highlighting the most relevant elements. "
    "Write the explanation as natural spoken language."
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _run_with_timeout(fn: Any, timeout: int) -> Any:
    """Run *fn* in a thread pool and enforce a hard timeout.

    Does NOT use 'with ThreadPoolExecutor' -- its __exit__ calls
    shutdown(wait=True) which hangs if the thread is stuck.
    """
    executor = ThreadPoolExecutor(max_workers=1)
    future   = executor.submit(fn)
    try:
        return future.result(timeout=timeout)
    finally:
        executor.shutdown(wait=False)


def _encode(image_path: str) -> bytes:
    return Path(image_path).read_bytes()


def _make_client() -> genai.Client:
    return genai.Client(api_key=get_api_key())


def _extract_json(text: str) -> dict:
    """Parse JSON from the raw Gemini response with 3 fallback tiers."""
    text = text.strip()
    # Tier 1: direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Tier 2: find a {...} block (handles accidental markdown fences)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    # Tier 3: treat whole response as plain explanation, no annotations
    return {"explanation": text, "annotations": []}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def query(image_path: str, question: str | None = None) -> str:
    """Send a screenshot to Gemini and return plain text.

    Parameters
    ----------
    image_path:
        Path to a PNG screenshot.
    question:
        Transcribed voice input; falls back to the config default prompt.
    """
    image_bytes = _encode(image_path)
    prompt      = question.strip() if question and question.strip() else get_prompt()
    model       = get_model()
    client      = _make_client()

    def _call() -> str:
        response = client.models.generate_content(
            model=model,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                types.Part.from_text(text=prompt),
            ],
        )
        return response.text or "(No response received)"

    try:
        return _run_with_timeout(_call, _TIMEOUT_SECONDS)
    except FuturesTimeoutError:
        print(f"[Clicky] ERROR: Gemini did not respond within {_TIMEOUT_SECONDS}s.", flush=True)
        return f"(Request timed out after {_TIMEOUT_SECONDS} seconds. Please try again.)"
    except Exception as exc:
        print(f"[Clicky] ERROR: Gemini API call failed: {exc}", flush=True)
        return f"(API error: {exc})"


def query_annotated(
    image_path: str,
    question: str | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Send a screenshot to Gemini; return (explanation, annotations).

    Parameters
    ----------
    image_path:
        Path to a PNG screenshot of the selected region.
    question:
        Optional spoken question from the user.

    Returns
    -------
    tuple[str, list[dict]]
        explanation  -- natural-language answer (speak via TTS).
        annotations  -- list of annotation dicts for annotate.draw_annotations().
    """
    image_bytes = _encode(image_path)
    model       = get_model()
    client      = _make_client()

    # User-facing content: just the question (or a neutral trigger).
    user_text = question.strip() if question and question.strip() else "Describe and annotate what you see."

    def _call() -> str:
        response = client.models.generate_content(
            model=model,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                types.Part.from_text(text=user_text),
            ],
            config=types.GenerateContentConfig(
                system_instruction=_ANNOTATION_SYSTEM,
                temperature=0.2,   # low temperature for consistent JSON output
            ),
        )
        return response.text or ""

    # Try once; on timeout, retry once with reduced timeout.
    raw = None
    for attempt, timeout in enumerate((_TIMEOUT_SECONDS, _RETRY_TIMEOUT_SECONDS)):
        try:
            raw = _run_with_timeout(_call, timeout)
            break
        except FuturesTimeoutError:
            if attempt == 0:
                print("[Clicky] Gemini timed out -- retrying...", flush=True)
            else:
                print(f"[Clicky] ERROR: Gemini did not respond after retry.", flush=True)
                return "(Request timed out. Please try again.)", []
        except Exception as exc:
            print(f"[Clicky] ERROR: Gemini API call failed: {exc}", flush=True)
            return f"(API error: {exc})", []

    if not raw:
        return "(No response received.)", []

    print(f"[Clicky] Raw Gemini response:\n{raw}", flush=True)
    parsed      = _extract_json(raw)
    explanation = str(parsed.get("explanation", raw) or raw)
    annotations = list(parsed.get("annotations", []))
    return explanation, annotations
