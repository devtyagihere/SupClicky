"""
Integration: Hotkey Listener + Thinking Orb
Connects Ctrl+F1 hotkey and pipeline events to spawn and update thinking orb overlay.
"""

from __future__ import annotations

import sys
import threading
import time
from pynput import keyboard

from orb_overlay import OrbState, ScreenOverlay


class HotKeyOrbManager:
    """Manages thinking orb lifecycle and state transitions."""

    def __init__(self) -> None:
        self.overlay: ScreenOverlay | None = None
        self.running = False
        self.overlay_thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def _start_overlay(self, state: OrbState = OrbState.THINKING, duration: float | None = None) -> None:
        """Start the overlay on a dedicated daemon thread."""
        # Ensure any old overlay is closed first
        if self.overlay:
            try:
                self.overlay.close()
            except Exception:
                pass
            self.overlay = None

        overlay = ScreenOverlay()
        overlay.set_state(state)
        self.overlay = overlay

        def _runner() -> None:
            try:
                overlay.show()
            except Exception as e:
                print(f"[Clicky] Error showing orb overlay: {e}", flush=True)
            finally:
                with self._lock:
                    if self.overlay is overlay:
                        self.overlay = None

        self.overlay_thread = threading.Thread(
            target=_runner,
            daemon=True,
            name="clicky-orb-overlay",
        )
        self.overlay_thread.start()

    def on_hotkey(self, key: object = None, state: OrbState = OrbState.THINKING, duration: float | None = None) -> None:
        """Triggered when Ctrl+F1 is pressed. Shows thinking orb."""
        print(f"[Clicky] Orb triggered with state: {state.value}", flush=True)
        with self._lock:
            if self.overlay and self.overlay.running:
                self.overlay.set_state(state)
            else:
                self._start_overlay(state=state, duration=duration)

    def show_thinking_orb(self, duration: float | None = None) -> None:
        """Show thinking orb (for Ctrl+F1 press or region selection)."""
        with self._lock:
            if self.overlay and self.overlay.running:
                self.overlay.set_state(OrbState.THINKING)
            else:
                self._start_overlay(OrbState.THINKING, duration=duration)

    def show_listening_orb(self, duration: float | None = None) -> None:
        """Show listening orb (while recording voice)."""
        with self._lock:
            if self.overlay and self.overlay.running:
                self.overlay.set_state(OrbState.LISTENING)
            else:
                self._start_overlay(OrbState.LISTENING, duration=duration)

    def show_analyzing_orb(self, duration: float | None = None) -> None:
        """Show analyzing orb (while calling Gemini API)."""
        with self._lock:
            if self.overlay and self.overlay.running:
                self.overlay.set_state(OrbState.ANALYZING)
            else:
                self._start_overlay(OrbState.ANALYZING, duration=duration)

    def show_done_orb(self, duration: float = 1.0) -> None:
        """Show done orb (when response is ready)."""
        with self._lock:
            if self.overlay and self.overlay.running:
                self.overlay.set_state(OrbState.DONE)

    def close_overlay(self) -> None:
        """Close overlay cleanly without hanging the app."""
        with self._lock:
            overlay = self.overlay
            thread = self.overlay_thread
            self.overlay = None
            self.overlay_thread = None

        if overlay:
            overlay.close()

        if thread and thread.is_alive() and threading.current_thread() != thread:
            thread.join(timeout=0.5)


class HotKeyListener:
    """Listen for Ctrl+F1 hotkey (standalone utility)."""

    def __init__(self, orb_manager: HotKeyOrbManager) -> None:
        self.orb_manager = orb_manager
        self.listener: keyboard.Listener | None = None
        self.running = False

    def on_press(self, key: object) -> None:
        """Handle key press"""
        try:
            if hasattr(key, "vk") and key.vk == 112:  # F1
                if hasattr(key, "ctrl") and key.ctrl:
                    self.orb_manager.show_thinking_orb()
        except Exception:
            pass

    def on_release(self, key: object) -> None:
        """Handle key release"""
        try:
            if hasattr(key, "vk") and key.vk == 113:  # F2
                if hasattr(key, "alt") and key.alt:
                    self.stop()
        except Exception:
            pass

    def start(self) -> None:
        """Start listening for hotkeys"""
        self.running = True
        self.listener = keyboard.Listener(
            on_press=self.on_press,
            on_release=self.on_release,
        )
        self.listener.start()
        print("[Clicky] Hotkey listener started (Ctrl+F1 to trigger orb)", flush=True)

    def stop(self) -> None:
        """Stop listening"""
        self.running = False
        if self.listener:
            self.listener.stop()
        print("[Clicky] Hotkey listener stopped", flush=True)


# ---------------------------------------------------------------------------
# Global singleton instance
# ---------------------------------------------------------------------------

_orb_manager_instance: HotKeyOrbManager | None = None
_manager_lock = threading.Lock()


def get_orb_manager() -> HotKeyOrbManager:
    """Return the shared HotKeyOrbManager instance."""
    global _orb_manager_instance
    with _manager_lock:
        if _orb_manager_instance is None:
            _orb_manager_instance = HotKeyOrbManager()
        return _orb_manager_instance


orb_manager = get_orb_manager()


def demo() -> None:
    """Demo: Show thinking orb with state transitions"""
    print("=" * 60)
    print("ScreenSense AI - Thinking Orb Demo")
    print("=" * 60)

    mgr = get_orb_manager()
    hotkey_listener = HotKeyListener(mgr)
    hotkey_listener.start()

    print("Press Ctrl+F1 to show thinking orb")
    print("Press Alt+F2 to quit")

    try:
        while hotkey_listener.running:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n[Clicky] Demo ended", flush=True)
    finally:
        hotkey_listener.stop()
        mgr.close_overlay()


if __name__ == "__main__":
    demo()
