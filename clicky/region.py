"""
region.py -- Interactive freehand lasso screen region selector.

Public API
----------
FreehandSelection:
    NamedTuple containing (points, bbox, screenshot).

select_region() -> FreehandSelection | None
    Shows a fullscreen overlay over the current screen with a crosshair cursor.
    The user draws any freehand shape by clicking and dragging.
    When the loop is closed (near the start point), it highlights the enclosed
    region.  Returns FreehandSelection or None if cancelled with Escape.
"""

from __future__ import annotations

import math
import time
import tkinter as tk
from typing import NamedTuple

from PIL import Image, ImageDraw, ImageEnhance, ImageTk
import mss
import mss.tools


class FreehandSelection(NamedTuple):
    points: list[tuple[int, int]]       # Absolute screen coordinates of drawn polygon
    bbox: tuple[int, int, int, int]     # (min_x, min_y, max_x, max_y)
    screenshot: Image.Image             # Clean full original screenshot


def select_region() -> FreehandSelection | None:
    """Show a fullscreen overlay and let the user draw a freehand shape.

    Returns
    -------
    FreehandSelection | None
        NamedTuple with points, bbox, and original screenshot, or None if
        the user cancelled with Escape or the drawn shape was too small.
    """
    # ── 1. Capture clean screenshot of primary monitor ────────────────────────
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        shot = sct.grab(monitor)
        offset_x: int = monitor["left"]
        offset_y: int = monitor["top"]
        width: int = monitor["width"]
        height: int = monitor["height"]

    orig_image = Image.frombytes("RGB", shot.size, shot.rgb)
    dimmed_image = ImageEnhance.Brightness(orig_image).enhance(0.4)

    # ── 2. Build the fullscreen Tkinter overlay ───────────────────────────────
    result: list[FreehandSelection | None] = [None]
    done: list[bool] = [False]

    root = tk.Tk()
    root.overrideredirect(True)
    root.geometry(f"{width}x{height}+{offset_x}+{offset_y}")
    root.attributes("-topmost", True)
    root.config(cursor="crosshair")

    canvas = tk.Canvas(root, width=width, height=height, highlightthickness=0)
    canvas.pack(fill=tk.BOTH, expand=True)

    tk_dimmed = ImageTk.PhotoImage(dimmed_image)
    bg_img_id = canvas.create_image(0, 0, anchor="nw", image=tk_dimmed)
    canvas.tk_dimmed = tk_dimmed  # prevent garbage collection

    # Top instructions banner
    canvas.create_rectangle(0, 0, width, 44, fill="#000000", outline="")
    banner_text_id = canvas.create_text(
        width // 2, 22,
        text="Click and drag to draw a freehand shape around anything    |    Esc to cancel",
        fill="#FFFFFF",
        font=("Segoe UI", 12, "bold"),
    )

    # ── 3. Freehand drawing state ─────────────────────────────────────────────
    is_drawing = False
    points: list[tuple[int, int]] = []
    line_ids: list[int] = []
    start_dot_id: int | None = None
    close_segment_id: int | None = None
    is_closed = False
    path_length = 0.0

    # ── 4. Mouse event handlers ───────────────────────────────────────────────
    def _on_press(event: tk.Event) -> None:  # type: ignore[type-arg]
        nonlocal is_drawing, points, line_ids, start_dot_id, close_segment_id, is_closed, path_length
        is_drawing = True
        is_closed = False
        path_length = 0.0

        # Clear any previous drawing
        for lid in line_ids:
            canvas.delete(lid)
        line_ids.clear()

        if start_dot_id is not None:
            canvas.delete(start_dot_id)
            start_dot_id = None

        if close_segment_id is not None:
            canvas.delete(close_segment_id)
            close_segment_id = None

        # Reset background back to dimmed
        canvas.itemconfig(bg_img_id, image=canvas.tk_dimmed)
        canvas.itemconfig(
            banner_text_id,
            text="Draw a freehand shape and loop back to the start point    |    Esc to cancel",
            fill="#FFFFFF",
        )

        points = [(event.x, event.y)]

        # Start marker (target circle to loop back to)
        start_dot_id = canvas.create_oval(
            event.x - 7, event.y - 7, event.x + 7, event.y + 7,
            outline="#00FFCC",
            fill="#002211",
            width=2,
        )

    def _on_drag(event: tk.Event) -> None:  # type: ignore[type-arg]
        nonlocal is_drawing, points, line_ids, close_segment_id, is_closed, path_length
        if not is_drawing or not points:
            return

        last_x, last_y = points[-1]
        dist = math.hypot(event.x - last_x, event.y - last_y)
        if dist < 3:
            return  # skip micro-movements for smooth performance

        points.append((event.x, event.y))
        path_length += dist

        # Draw real-time line segment
        line_color = "#00FF41" if is_closed else "#00FFCC"
        lid = canvas.create_line(
            last_x, last_y, event.x, event.y,
            fill=line_color,
            width=2,
            capstyle=tk.ROUND,
            joinstyle=tk.ROUND,
        )
        line_ids.append(lid)

        # Check for loop closure (within 28px of start after traveling at least 60px)
        start_x, start_y = points[0]
        dist_to_start = math.hypot(event.x - start_x, event.y - start_y)

        if len(points) >= 15 and path_length >= 60 and dist_to_start <= 28:
            if not is_closed:
                is_closed = True
                # Draw snap-close line to start point
                if close_segment_id is None:
                    close_segment_id = canvas.create_line(
                        event.x, event.y, start_x, start_y,
                        fill="#00FF41",
                        width=3,
                        capstyle=tk.ROUND,
                    )

                # Turn start dot and lines neon green
                if start_dot_id is not None:
                    canvas.itemconfig(start_dot_id, fill="#00FF41", outline="#FFFFFF", width=3)
                for line in line_ids:
                    canvas.itemconfig(line, fill="#00FF41", width=3)

                # Highlight the enclosed region: pixels inside shape light up to full brightness!
                try:
                    mask = Image.new("L", (width, height), 0)
                    ImageDraw.Draw(mask).polygon(points, fill=255)
                    highlighted_bg = dimmed_image.copy()
                    highlighted_bg.paste(orig_image, (0, 0), mask=mask)
                    tk_highlighted = ImageTk.PhotoImage(highlighted_bg)
                    canvas.itemconfig(bg_img_id, image=tk_highlighted)
                    canvas.tk_highlighted = tk_highlighted
                except Exception:
                    pass

                canvas.itemconfig(
                    banner_text_id,
                    text="Shape closed and highlighted! Release mouse to finish.",
                    fill="#00FF41",
                )
            else:
                # Update snap closing line position
                if close_segment_id is not None:
                    canvas.coords(close_segment_id, event.x, event.y, start_x, start_y)
        elif is_closed and dist_to_start > 38:
            # User moved away from the start point -- un-close
            is_closed = False
            if close_segment_id is not None:
                canvas.delete(close_segment_id)
                close_segment_id = None
            if start_dot_id is not None:
                canvas.itemconfig(start_dot_id, fill="#002211", outline="#00FFCC", width=2)
            for line in line_ids:
                canvas.itemconfig(line, fill="#00FFCC", width=2)
            canvas.itemconfig(bg_img_id, image=canvas.tk_dimmed)
            canvas.itemconfig(
                banner_text_id,
                text="Draw a freehand shape and loop back to the start point    |    Esc to cancel",
                fill="#FFFFFF",
            )

    def _on_release(event: tk.Event) -> None:  # type: ignore[type-arg]
        nonlocal is_drawing, points, is_closed, done
        if not is_drawing or len(points) < 5:
            is_drawing = False
            return

        is_drawing = False

        # If user released without closing exactly, auto-close the shape
        if not is_closed:
            points.append(points[0])
            is_closed = True

        # Calculate bounding box
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        min_x = max(0, min(xs))
        min_y = max(0, min(ys))
        max_x = min(width, max(xs))
        max_y = min(height, max(ys))

        if (max_x - min_x) >= 10 and (max_y - min_y) >= 10:
            abs_points = [(p[0] + offset_x, p[1] + offset_y) for p in points]
            screen_bbox = (min_x + offset_x, min_y + offset_y, max_x + offset_x, max_y + offset_y)
            result[0] = FreehandSelection(
                points=abs_points,
                bbox=screen_bbox,
                screenshot=orig_image,
            )

        done[0] = True

    def _on_escape(_event: tk.Event) -> None:  # type: ignore[type-arg]
        nonlocal done
        done[0] = True

    canvas.bind("<ButtonPress-1>", _on_press)
    canvas.bind("<B1-Motion>", _on_drag)
    canvas.bind("<ButtonRelease-1>", _on_release)
    root.bind("<Escape>", _on_escape)

    # ── 5. Manual update loop ─────────────────────────────────────────────────
    while not done[0]:
        try:
            root.update()
        except tk.TclError:
            break
        time.sleep(0.005)

    try:
        root.destroy()
    except Exception:
        pass

    return result[0]
