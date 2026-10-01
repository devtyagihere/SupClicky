"""
main.py -- Clicky entry point.

Run with:
    python main.py

Press Ctrl+F1 to trigger the pipeline:
    1. Show thinking orb with THINKING state
    2. Show a freehand lasso overlay (click and drag to draw, close loop to finish, Esc to cancel)
    3. Crop only the pixels inside the drawn freehand shape (shows orb with THINKING state)
    4. Listen for your spoken question (switches orb to LISTENING state)
    5. Send cropped region + question to Gemini (switches orb to ANALYZING state)
    6. When response is ready, switch orb to DONE state for 1 second, then close orb
    7. Draw visual annotations on screen (arrows, rectangles, circles, text labels)
    8. Speak the explanation aloud -- tts closes orb when voice starts playing

Press Alt+F1 to quit.
"""

from __future__ import annotations

import os
import time

from clicky import annotate, capture, gemini_client, hotkey, region, tts, voice
from clicky.config import get_annotation_duration
from orb_integration import orb_manager


def pipeline() -> None:
    """Run one full freehand-select -> voice -> Gemini -> annotate + TTS cycle."""
    image_path: str | None = None
    try:
        # 1. When Ctrl+F1 is pressed, show thinking orb with THINKING state
        print("[Clicky] Ctrl+F1 pressed -- showing thinking orb with THINKING state...", flush=True)
        orb_manager.show_thinking_orb()

        # Brief pause so the hotkey overlay doesn't appear in the screenshot.
        time.sleep(0.3)

        # ── Freehand lasso selection ──────────────────────────────────────────
        print("[Clicky] Draw a freehand shape on screen (drag to draw, close loop to finish)...", flush=True)
        selection = region.select_region()

        if selection is None:
            print("[Clicky] Selection cancelled.", flush=True)
            orb_manager.close_overlay()
            return

        print(f"[Clicky] Freehand shape captured: {len(selection.points)} points, bbox={selection.bbox}", flush=True)

        # ── Crop pixels inside drawn shape (shows orb with THINKING state) ───
        print("[Clicky] Cropping pixels inside drawn shape...", flush=True)
        image_path = capture.take_freehand_screenshot(
            selection.points,
            selection.bbox,
            selection.screenshot,
        )

        # ── Voice input: During voice recording, switch to LISTENING state ────
        print("[Clicky] Voice recording -- switching orb to LISTENING state...", flush=True)
        orb_manager.show_listening_orb()
        question = voice.listen()
        if question:
            print(f"[Clicky] You asked: {question!r}", flush=True)
        else:
            print("[Clicky] No speech detected -- using annotation prompt.", flush=True)

        # ── Gemini: During Gemini API call, show ANALYZING state ──────────────
        print("[Clicky] Querying Gemini -- switching orb to ANALYZING state...", flush=True)
        orb_manager.show_analyzing_orb()
        explanation, annotations = gemini_client.query_annotated(
            image_path,
            question=question or None,
        )

        print(f"[Clicky] Explanation: {explanation}", flush=True)
        print(f"[Clicky] Annotations: {len(annotations)} item(s)", flush=True)

        # ── Response ready: show DONE state for 1 second then close ───────────
        print("[Clicky] Response ready -- showing DONE state for 1 second...", flush=True)
        orb_manager.show_done_orb()
        time.sleep(1.0)
        orb_manager.close_overlay()

        # ── Draw annotations (non-blocking -- runs in daemon thread) ──────────
        duration = get_annotation_duration()
        annotate.draw_annotations(annotations, selection.bbox, duration=duration)

        # ── TTS (voice response starts playing, closes orb cleanly) ───────────
        tts.speak(explanation)

    finally:
        # Make sure orb closes cleanly without hanging the app
        orb_manager.close_overlay()
        if image_path and os.path.exists(image_path):
            os.remove(image_path)


def main() -> None:
    print("[Clicky] Starting up -- press Ctrl-C to quit.", flush=True)
    hotkey.start(pipeline)


if __name__ == "__main__":
    main()
