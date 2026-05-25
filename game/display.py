"""窗口缩放、全屏与逻辑坐标映射（设计分辨率 960×640）。"""

from __future__ import annotations

import json

import pygame

import config
from game.layout import init_layout
from game.platform_util import is_web

_SETTINGS_PATH = config.ROOT / "display.json"
_LETTERBOX = (14, 16, 22)


class DisplayManager:
    """渲染到固定逻辑画布，再按比例缩放至窗口（保持宽高比）。"""

    def __init__(self) -> None:
        if is_web():
            init_layout()
        self.design_w = config.WIDTH
        self.design_h = config.HEIGHT
        self.fullscreen = False
        self.window_w = self.design_w
        self.window_h = self.design_h
        self._load_settings()
        self.surface = pygame.Surface((self.design_w, self.design_h))
        self.screen: pygame.Surface
        self.scale = 1.0
        self.dest_rect = pygame.Rect(0, 0, self.design_w, self.design_h)
        self._create_screen()

    def _load_settings(self) -> None:
        try:
            if _SETTINGS_PATH.is_file():
                data = json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
                self.window_w = int(data.get("window_w", self.design_w))
                self.window_h = int(data.get("window_h", self.design_h))
                self.fullscreen = bool(data.get("fullscreen", False))
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            pass
        self.window_w = max(config.WINDOW_MIN_W, min(3840, self.window_w))
        self.window_h = max(config.WINDOW_MIN_H, min(2160, self.window_h))

    def save_settings(self) -> None:
        try:
            if not self.fullscreen:
                w, h = self.screen.get_size()
                self.window_w, self.window_h = w, h
            payload = {
                "window_w": self.window_w,
                "window_h": self.window_h,
                "fullscreen": self.fullscreen,
            }
            _SETTINGS_PATH.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass

    def _create_screen(self) -> None:
        if is_web():
            self.fullscreen = False
            self.screen = pygame.display.set_mode((self.design_w, self.design_h))
            try:
                self.screen.set_colorkey(None)
            except Exception:
                pass
            self.surface = self.screen
            self.scale = 1.0
            self.dest_rect = pygame.Rect(0, 0, self.design_w, self.design_h)
            return
        if self.fullscreen:
            info = pygame.display.Info()
            size = (info.current_w, info.current_h)
            flags = pygame.FULLSCREEN
        else:
            size = (self.window_w, self.window_h)
            flags = pygame.RESIZABLE
        self.screen = pygame.display.set_mode(size, flags)
        self._update_transform()

    def _update_transform(self) -> None:
        sw, sh = self.screen.get_size()
        scale = min(sw / self.design_w, sh / self.design_h)
        self.scale = max(0.35, scale)
        dw = max(1, int(self.design_w * self.scale))
        dh = max(1, int(self.design_h * self.scale))
        self.dest_rect = pygame.Rect((sw - dw) // 2, (sh - dh) // 2, dw, dh)

    def on_resize(self, width: int, height: int) -> None:
        if is_web() or self.fullscreen:
            return
        self.window_w = max(config.WINDOW_MIN_W, width)
        self.window_h = max(config.WINDOW_MIN_H, height)
        self.screen = pygame.display.set_mode(
            (self.window_w, self.window_h), pygame.RESIZABLE
        )
        self._update_transform()

    def toggle_fullscreen(self) -> bool:
        if is_web():
            return False
        if not self.fullscreen:
            self.window_w, self.window_h = self.screen.get_size()
        self.fullscreen = not self.fullscreen
        self._create_screen()
        return self.fullscreen

    def to_game(self, mx: int, my: int) -> tuple[int, int] | None:
        if not self.dest_rect.collidepoint(mx, my):
            return None
        gx = int((mx - self.dest_rect.x) / self.scale)
        gy = int((my - self.dest_rect.y) / self.scale)
        gx = max(0, min(self.design_w - 1, gx))
        gy = max(0, min(self.design_h - 1, gy))
        return gx, gy

    def game_mouse_pos(self) -> tuple[int, int] | None:
        return self.to_game(*pygame.mouse.get_pos())

    def present(self) -> None:
        if is_web():
            pygame.event.pump()
            pygame.display.flip()
            pygame.display.update()
            try:
                import platform as pw

                pw.window.window_resize()
                if config.PORTRAIT:
                    pw.document.body.style.margin = "0"
            except Exception:
                pass
            return
        self.screen.fill(_LETTERBOX)
        if self.dest_rect.width == self.design_w and self.dest_rect.height == self.design_h:
            self.screen.blit(self.surface, self.dest_rect.topleft)
        else:
            scaled = pygame.transform.smoothscale(
                self.surface, (self.dest_rect.width, self.dest_rect.height)
            )
            self.screen.blit(scaled, self.dest_rect.topleft)
        pygame.display.flip()
