"""
annotate.py -- Draws visual annotations on a transparent screen overlay.

Public API
----------
draw_annotations(annotations, bbox, duration) -> None
    Draws arrows, rectangles, circles, and text labels on a transparent
    fullscreen window positioned on top of all other windows.
    Annotations are held for (duration - 1) seconds then fade to nothing
    over 1 second.  Returns immediately -- the overlay runs in a daemon
    thread so it never blocks the pipeline or TTS.
"""

from __future__ import annotations

import threading
import time
import tkinter as tk
from typing import Any

import mss


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def draw_annotations(
    annotations: list[dict[str, Any]],
    bbox: tuple[int, int, int, int],
    duration: int = 5,
) -> None:
    """Draw annotations on screen; return immediately.

    Parameters
    ----------
    annotations:
        List of annotation dicts produced by ``gemini_client.query_annotated()``.
        Each dict has at minimum a ``"type"`` key.
    bbox:
        (x1, y1, x2, y2) in absolute screen coordinates of the captured region.
        Annotation coordinates are normalised relative to this region.
    duration:
        Total seconds the overlay stays on screen (including 1-second fade).
    """
    if not annotations:
        return

    threading.Thread(
        target=_overlay_thread,
        args=(annotations, bbox, duration),
        daemon=True,
        name="clicky-annotate",
    ).start()


# ---------------------------------------------------------------------------
# Internal implementation
# ---------------------------------------------------------------------------

def _overlay_thread(
    annotations: list[dict[str, Any]],
    bbox: tuple[int, int, int, int],
    duration: int,
) -> None:
    """Run in a daemon thread -- draws overlay, holds, fades, destroys."""
    bx, by, bx2, by2 = bbox
    bw = bx2 - bx
    bh = by2 - by

    # Full primary monitor dimensions for the overlay window.
    with mss.mss() as sct:
        mon = sct.monitors[1]
        sw: int = mon["width"]
        sh: int = mon["height"]
        ox: int = mon["left"]
        oy: int = mon["top"]

    def _to_canvas(nx: float, ny: float) -> tuple[int, int]:
        """Normalised image coords -> canvas (window-relative) coords."""
        return int(bx + nx * bw) - ox, int(by + ny * bh) - oy

    # ── Build the tkinter overlay ─────────────────────────────────────────
    root = tk.Tk()
    root.overrideredirect(True)
    root.geometry(f"{sw}x{sh}+{ox}+{oy}")
    root.attributes("-topmost", True)
    # 'black' pixels are rendered as fully transparent (click-through) on Windows.
    root.attributes("-transparentcolor", "black")
    root.configure(bg="black")

    canvas = tk.Canvas(root, bg="black", highlightthickness=0)
    canvas.pack(fill=tk.BOTH, expand=True)

    # ── Draw every annotation ─────────────────────────────────────────────
    for ann in annotations:
        _draw_one(canvas, ann, _to_canvas, bw, bh)

    root.attributes("-alpha", 0.92)

    # ── Animate: hold then fade ───────────────────────────────────────────
    hold_end  = time.monotonic() + max(duration - 1.0, 0.5)
    fade_end  = hold_end + 1.0

    while True:
        try:
            root.update()
        except tk.TclError:
            break

        now = time.monotonic()
        if now >= fade_end:
            break
        elif now >= hold_end:
            progress = (now - hold_end) / 1.0          # 0 → 1 over last second
            alpha = max(0.0, 0.92 * (1.0 - progress))
            try:
                root.attributes("-alpha", alpha)
            except tk.TclError:
                break

        time.sleep(0.016)                               # ~60 fps

    try:
        root.destroy()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Per-shape rendering helpers
# ---------------------------------------------------------------------------

def _draw_one(
    canvas: tk.Canvas,
    ann: dict[str, Any],
    to_canvas: Any,
    bw: int,
    bh: int,
) -> None:
    kind   = ann.get("type", "")
    color  = ann.get("color", "#FFFF44")
    label  = ann.get("label", "")

    if kind == "rectangle":
        x1, y1 = to_canvas(ann.get("x1", 0.0), ann.get("y1", 0.0))
        x2, y2 = to_canvas(ann.get("x2", 1.0), ann.get("y2", 1.0))
        canvas.create_rectangle(x1, y1, x2, y2, outline=color, width=3, fill="")
        if label:
            _text_label(canvas, label, x1, y1 - 4, color, anchor="sw")

    elif kind == "circle":
        cx, cy = to_canvas(ann.get("cx", 0.5), ann.get("cy", 0.5))
        r_norm = float(ann.get("r", 0.06))
        r_px   = int(r_norm * min(bw, bh))
        canvas.create_oval(
            cx - r_px, cy - r_px, cx + r_px, cy + r_px,
            outline=color, width=3, fill="",
        )
        if label:
            _text_label(canvas, label, cx, cy - r_px - 4, color, anchor="s")

    elif kind == "arrow":
        x1, y1 = to_canvas(ann.get("x1", 0.2), ann.get("y1", 0.9))
        x2, y2 = to_canvas(ann.get("x2", 0.5), ann.get("y2", 0.5))
        canvas.create_line(
            x1, y1, x2, y2,
            fill=color, width=3,
            arrow=tk.LAST, arrowshape=(18, 22, 7),
        )
        if label:
            _text_label(canvas, label, x1, y1 + 4, color, anchor="nw")

    elif kind == "text":
        x, y = to_canvas(ann.get("x", 0.1), ann.get("y", 0.1))
        if label:
            _text_label(canvas, label, x, y, color, anchor="nw")


def _text_label(
    canvas: tk.Canvas,
    text: str,
    x: int,
    y: int,
    color: str,
    anchor: str = "nw",
) -> None:
    """Draw text with a dark shadow for readability on any background."""
    font = ("Segoe UI", 12, "bold")
    # Shadow (offset by 2 px)
    canvas.create_text(x + 2, y + 2, text=text, fill="#000000", font=font, anchor=anchor)
    # Coloured foreground
    canvas.create_text(x,     y,     text=text, fill=color,    font=font, anchor=anchor)
