"""
capture.py -- Screenshot capture (full screen, rectangle, and freehand polygon).

Public API
----------
take_screenshot() -> str
    Captures the full primary monitor, writes it to a temp PNG file,
    and returns the absolute file path.

take_region_screenshot(bbox) -> str
    Captures a specific rectangular region of the screen, writes it to
    a temp PNG file, and returns the absolute file path.

take_freehand_screenshot(points, bbox, screenshot=None) -> str
    Crops only the pixels inside the drawn freehand polygon shape.
    Pixels outside the polygon are made transparent (RGBA).
    Shows orb with THINKING state when region is selected.
    Writes to a temp PNG file and returns the absolute file path.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import mss
import mss.tools
from PIL import Image, ImageDraw


def _notify_orb_thinking() -> None:
    """When user selects region, show orb with THINKING state."""
    try:
        from orb_integration import get_orb_manager
        get_orb_manager().show_thinking_orb()
    except Exception:
        pass


def take_screenshot() -> str:
    """Capture the full screen and save it to a temporary PNG file."""
    _notify_orb_thinking()
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        screenshot = sct.grab(monitor)

    tmp = tempfile.NamedTemporaryFile(
        suffix=".png",
        prefix="clicky_",
        delete=False,
    )
    tmp.close()
    mss.tools.to_png(screenshot.rgb, screenshot.size, output=tmp.name)
    return str(Path(tmp.name).resolve())


def take_region_screenshot(bbox: tuple[int, int, int, int]) -> str:
    """Capture a rectangular screen region and save it to a temporary PNG file."""
    _notify_orb_thinking()
    x1, y1, x2, y2 = bbox
    region = {"left": x1, "top": y1, "width": x2 - x1, "height": y2 - y1}

    with mss.mss() as sct:
        screenshot = sct.grab(region)

    tmp = tempfile.NamedTemporaryFile(
        suffix=".png",
        prefix="clicky_region_",
        delete=False,
    )
    tmp.close()
    mss.tools.to_png(screenshot.rgb, screenshot.size, output=tmp.name)
    return str(Path(tmp.name).resolve())


def take_freehand_screenshot(
    points: list[tuple[int, int]],
    bbox: tuple[int, int, int, int],
    screenshot: Image.Image | None = None,
) -> str:
    """Capture and crop only the pixels enclosed within the freehand polygon.

    Parameters
    ----------
    points:
        Absolute screen coordinates of the polygon vertices.
    bbox:
        (min_x, min_y, max_x, max_y) of the polygon in screen coordinates.
    screenshot:
        Optional pre-captured PIL Image of the screen.  If None, grabs
        the screen immediately via mss.

    Returns
    -------
    str
        Absolute path to the temporary PNG file.  Pixels outside the
        drawn polygon are transparent.
    """
    # When user selects region, show orb with THINKING state
    _notify_orb_thinking()

    min_x, min_y, max_x, max_y = bbox
    width = max_x - min_x
    height = max_y - min_y

    if screenshot is None:
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            shot = sct.grab(monitor)
            screenshot = Image.frombytes("RGB", shot.size, shot.rgb)

    # 1. Crop to bounding box
    cropped = screenshot.crop((min_x, min_y, max_x, max_y)).convert("RGBA")

    # 2. Build polygon mask relative to bounding box
    rel_points = [(x - min_x, y - min_y) for (x, y) in points]
    mask = Image.new("L", (width, height), 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.polygon(rel_points, fill=255)

    # 3. Create RGBA image with transparent background outside polygon
    output = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    output.paste(cropped, (0, 0), mask=mask)

    # 4. Save to temporary PNG file
    tmp = tempfile.NamedTemporaryFile(
        suffix=".png",
        prefix="clicky_freehand_",
        delete=False,
    )
    tmp.close()
    output.save(tmp.name, format="PNG")
    return str(Path(tmp.name).resolve())
