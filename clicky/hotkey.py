"""
hotkey.py — Global hotkey listener.

Public API
----------
start(callback: Callable[[], None]) -> None
    Registers the configured hotkey and starts listening in the background.
    *callback* is invoked in a fresh daemon thread each time the hotkey fires.
    This function blocks forever (call it as the last step in main).
"""

from __future__ import annotations

import ctypes
import os
import sys
import threading
import traceback
from typing import Callable

from pynput import keyboard

from clicky.config import get_hotkey, get_quit_hotkey


def _check_admin() -> None:
    """Warn if not running as Administrator.

    On Windows, pynput's low-level keyboard hook can silently receive no
    events when the process lacks elevated privileges — particularly when
    the foreground window belongs to an elevated process (e.g. Task Manager).
    This does not exit; it just prints a clear warning.
    """
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
    except AttributeError:
        return  # Not on Windows — skip the check.

    if not is_admin:
        print(
            "[Clicky] WARNING: Not running as Administrator.\n"
            "         If the hotkey does nothing, re-run this terminal as Admin:\n"
            "         Right-click PowerShell -> 'Run as administrator', then retry.",
            flush=True,
        )


def start(callback: Callable[[], None]) -> None:
    """Register the global hotkey and block until the process exits."""
    _check_admin()

    _busy = threading.Lock()

    def _on_hotkey() -> None:
        # ── Confirm the OS delivered the keypress to pynput ─────────────────
        print("[Clicky] Hotkey detected!", flush=True)

        if not _busy.acquire(blocking=False):
            print("[Clicky] Pipeline already running — ignoring extra press.", flush=True)
            return

        print("[Clicky] Lock acquired — spawning worker thread.", flush=True)

        def _run() -> None:
            try:
                callback()
            except Exception:  # noqa: BLE001
                # Full traceback so nothing is silently swallowed.
                print("[Clicky] Pipeline raised an exception:", flush=True)
                traceback.print_exc(file=sys.stdout)
            finally:
                _busy.release()
                print("[Clicky] Lock released.", flush=True)

        thread = threading.Thread(target=_run, daemon=True, name="clicky-pipeline")
        thread.start()
        print(f"[Clicky] Worker thread started (id={thread.ident}).", flush=True)

    hotkey_str = get_hotkey()
    quit_str = get_quit_hotkey()
    print(f"[Clicky] Registering trigger hotkey : {hotkey_str!r}", flush=True)
    print(f"[Clicky] Registering quit hotkey    : {quit_str!r}", flush=True)

    def _on_quit() -> None:
        print("[Clicky] Quit hotkey pressed — terminating process now.", flush=True)
        os._exit(0)  # kills all threads immediately, including a stuck pipeline

    try:
        listener = keyboard.GlobalHotKeys({
            hotkey_str: _on_hotkey,
            quit_str:   _on_quit,
        })
    except Exception:
        print("[Clicky] ERROR: Failed to create GlobalHotKeys listener:", flush=True)
        traceback.print_exc(file=sys.stdout)
        return

    print(
        "[Clicky] Listener ready.\n"
        f"         Press {hotkey_str} to capture + ask Gemini.\n"
        f"         Press {quit_str} to quit.",
        flush=True,
    )
    with listener:
        listener.join()
