"""
ScreenSense AI - Thinking Orb Overlay (60 FPS)
Animated glowing orb with particles and state transitions
Uses pygame for smooth 60 FPS animation with transparent background on Windows.
"""

from __future__ import annotations

import ctypes
import math
import os
import sys
import threading
import time
from enum import Enum

import pygame

# Background clear color -- keyed out as transparent on Windows
BG_COLOR = (10, 10, 20)


class OrbState(Enum):
    """Orb animation states"""
    THINKING = "thinking"
    LISTENING = "listening"
    ANALYZING = "analyzing"
    DONE = "done"


class Particle:
    """Single particle orbiting the orb"""
    def __init__(self, angle: float, distance: float, speed: float) -> None:
        self.angle = angle
        self.distance = distance
        self.speed = speed  # radians per frame
        self.life = 1.0  # alpha

    def update(self) -> None:
        self.angle += self.speed
        if self.angle > 2 * math.pi:
            self.angle -= 2 * math.pi

    def get_position(self, center_x: int, center_y: int) -> tuple[int, int]:
        x = center_x + self.distance * math.cos(self.angle)
        y = center_y + self.distance * math.sin(self.angle)
        return int(x), int(y)


class ThinkingOrb:
    """60 FPS animated thinking orb"""

    def __init__(self, width: int = 1920, height: int = 1080) -> None:
        self.width = width
        self.height = height
        self.center_x = width // 2
        self.center_y = height // 2

        # Animation state
        self.frame = 0
        self.state = OrbState.THINKING
        self.running = False

        # Orb properties
        self.orb_radius = 75.0  # pixels
        self.min_radius = 60.0
        self.max_radius = 90.0
        self.rotation = 0.0
        self.pulse = 0.0
        self.glow_alpha = 1.0

        # Particles
        self.particles: list[Particle] = []
        self.create_particles()

        # Colors (gradient)
        self.colors = [
            (0, 100, 255),      # Blue
            (100, 50, 255),     # Purple
            (0, 200, 255),      # Cyan
            (100, 100, 255),    # Light blue
        ]

        # FPS counter
        self.frame_count = 0
        self.fps_start = time.time()
        self.current_fps = 0.0

    def create_particles(self) -> None:
        """Create orbiting particles around orb"""
        self.particles = []
        num_particles = 12
        for i in range(num_particles):
            angle = (2 * math.pi * i) / num_particles
            distance = self.orb_radius + 50
            speed = 0.05 + (i % 3) * 0.01  # Varying speeds
            self.particles.append(Particle(angle, distance, speed))

    def update(self) -> None:
        """Update animation state"""
        self.frame += 1

        # Rotation: Full rotation every 2 seconds (120 frames at 60 FPS)
        self.rotation = (self.frame % 120) / 120 * (2 * math.pi)

        # Pulse: Oscillate between min and max radius
        self.pulse = math.sin(self.frame * 0.05) * (self.max_radius - self.min_radius) / 2
        self.orb_radius = (self.min_radius + self.max_radius) / 2 + self.pulse

        # Update particles
        for particle in self.particles:
            particle.update()

        # Glow pulsing
        self.glow_alpha = 0.5 + 0.5 * math.sin(self.frame * 0.03)

        # FPS calculation
        self.frame_count += 1
        elapsed = time.time() - self.fps_start
        if elapsed >= 1.0:
            self.current_fps = self.frame_count / elapsed
            self.frame_count = 0
            self.fps_start = time.time()

    def get_state_text(self) -> str:
        """Get text based on current state"""
        states = {
            OrbState.THINKING: "Thinking...",
            OrbState.LISTENING: "Listening...",
            OrbState.ANALYZING: "Analyzing...",
            OrbState.DONE: "Done!",
        }
        return states.get(self.state, "Processing...")

    def draw_to_surface(self, surface: pygame.Surface) -> None:
        """Draw orb directly to pygame surface"""
        center_x = surface.get_width() // 2
        center_y = surface.get_height() // 2

        # Draw outer glow rings
        glow_colors = [
            (20, 60, 150),      # Dark blue glow
            (40, 100, 200),     # Medium blue
            (60, 150, 255),     # Light blue
        ]

        for i, (r, g, b) in enumerate(glow_colors):
            glow_size = int(self.orb_radius + (i + 1) * 20)
            pygame.draw.circle(
                surface,
                (r, g, b),
                (center_x, center_y),
                glow_size,
            )

        # Draw main orb with gradient effect (concentric circles)
        max_r = max(1, int(self.orb_radius))
        for radius in range(max_r, 0, -2):
            ratio = radius / max_r
            r = int(self.colors[0][0] * ratio + self.colors[1][0] * (1 - ratio))
            g = int(self.colors[0][1] * ratio + self.colors[2][1] * (1 - ratio))
            b = int(self.colors[0][2] * ratio + self.colors[3][2] * (1 - ratio))

            pygame.draw.circle(
                surface,
                (r, g, b),
                (center_x, center_y),
                radius,
            )

        # Draw inner bright core
        core_size = int(self.orb_radius * 0.4)
        pygame.draw.circle(
            surface,
            (255, 255, 255),
            (center_x, center_y),
            core_size,
        )

        # Draw particles
        for particle in self.particles:
            px, py = particle.get_position(center_x, center_y)
            pygame.draw.circle(
                surface,
                (100, 200, 255),
                (int(px), int(py)),
                3,
            )


class ScreenOverlay:
    """Full-screen transparent overlay with thinking orb"""

    def __init__(self, width: int | None = None, height: int | None = None) -> None:
        if width is None or height is None:
            try:
                import mss
                with mss.mss() as sct:
                    mon = sct.monitors[1]
                    width = int(mon["width"])
                    height = int(mon["height"])
            except Exception:
                width = 1920
                height = 1080

        self.width = width
        self.height = height
        self.orb = ThinkingOrb(width, height)
        self.running = False
        self.screen: pygame.Surface | None = None
        self.clock: pygame.time.Clock | None = None
        self.font: pygame.font.Font | None = None

    def create_overlay(self) -> None:
        """Create pygame window with borderless transparent overlay"""
        os.environ["SDL_VIDEO_WINDOW_POS"] = "0,0"
        pygame.init()
        self.clock = pygame.time.Clock()

        # Borderless window
        self.screen = pygame.display.set_mode((self.width, self.height), pygame.NOFRAME)
        pygame.display.set_caption("ScreenSense AI - Thinking...")

        # On Windows: make BG_COLOR completely transparent (click-through) & topmost
        if sys.platform == "win32":
            try:
                hwnd = pygame.display.get_wm_info().get("window")
                if hwnd:
                    GWL_EXSTYLE = -20
                    WS_EX_LAYERED = 0x80000
                    LWA_COLORKEY = 0x1
                    HWND_TOPMOST = -1
                    SWP_NOMOVE = 0x2
                    SWP_NOSIZE = 0x1

                    user32 = ctypes.windll.user32
                    wl = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, wl | WS_EX_LAYERED)

                    # COLORREF format 0x00BBGGRR for BG_COLOR
                    r, g, b = BG_COLOR
                    colorkey = r | (g << 8) | (b << 16)
                    user32.SetLayeredWindowAttributes(hwnd, colorkey, 0, LWA_COLORKEY)
                    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
            except Exception as e:
                print(f"[Clicky] Layered window warning: {e}", flush=True)

        try:
            self.font = pygame.font.Font(None, 36)
        except Exception:
            self.font = pygame.font.Font(None, 36)

    def animate(self) -> None:
        """Animation loop (60 FPS)"""
        self.running = True
        try:
            while self.running and self.screen:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                    elif event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            self.running = False

                if not self.running:
                    break

                self.orb.update()
                self.render_frame()

                if self.clock:
                    self.clock.tick(60)
        except Exception as e:
            print(f"[Clicky] Orb animation error: {e}", flush=True)
        finally:
            self.running = False
            try:
                pygame.display.quit()
                pygame.quit()
            except Exception:
                pass
            self.screen = None

    def render_frame(self) -> None:
        """Render single frame"""
        try:
            if not self.screen:
                return

            # Clear screen with colorkey transparent background
            self.screen.fill(BG_COLOR)

            # Draw orb
            self.orb.draw_to_surface(self.screen)

            # Draw text label
            text = self.orb.get_state_text()
            if self.font:
                text_surf = self.font.render(text, True, (0, 255, 200))
                text_rect = text_surf.get_rect(
                    center=(self.orb.center_x, self.orb.center_y + 150)
                )
                self.screen.blit(text_surf, text_rect)

                # Draw FPS counter
                fps_text = self.font.render(
                    f"FPS: {self.orb.current_fps:.1f}",
                    True,
                    (255, 255, 255),
                )
                self.screen.blit(fps_text, (20, 20))

            pygame.display.flip()

        except Exception as e:
            print(f"[Clicky] Orb render error: {e}", flush=True)

    def show(self) -> None:
        """Show overlay and start animation"""
        self.create_overlay()
        self.animate()

    def close(self) -> None:
        """Close overlay cleanly without hanging"""
        self.running = False

    def set_state(self, state: OrbState) -> None:
        """Change orb state"""
        self.orb.state = state

    def wait_until_closed(self) -> None:
        """Block until overlay is closed"""
        pass


if __name__ == "__main__":
    print("[Clicky] ScreenSense AI - Thinking Orb Demo")
    print("Press ESC to close the window")
    overlay = ScreenOverlay()
    try:
        overlay.show()
    except KeyboardInterrupt:
        print("[Clicky] Demo closed")
        overlay.close()
