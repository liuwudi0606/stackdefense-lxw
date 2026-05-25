"""横屏 / 竖屏布局：手机竖屏自动切换逻辑分辨率。"""

from __future__ import annotations

import sys

import config


def _viewport_aspect() -> float | None:
    """返回 高/宽；无法检测时 None。"""
    if sys.platform in ("emscripten", "wasi"):
        try:
            import platform as pw

            w = int(getattr(pw.window, "innerWidth", 0) or 0)
            h = int(getattr(pw.window, "innerHeight", 0) or 0)
            if w > 0 and h > 0:
                return h / w
        except Exception:
            pass
        try:
            import pygame

            info = pygame.display.Info()
            if info.current_w > 0 and info.current_h > 0:
                return info.current_h / info.current_w
        except Exception:
            pass
    return None


def should_use_portrait() -> bool:
    """竖屏设备或窄高窗口时使用竖屏布局。"""
    if sys.platform in ("emscripten", "wasi"):
        try:
            import platform as pw

            loc = pw.window.location
            if "portrait" in (loc.hash or "") or "portrait" in (loc.search or ""):
                return True
        except Exception:
            pass
    ar = _viewport_aspect()
    if ar is not None:
        return ar > 1.12
    return False


def init_layout(force_portrait: bool | None = None) -> bool:
    """应用布局；返回是否为竖屏。"""
    portrait = should_use_portrait() if force_portrait is None else force_portrait
    config.apply_layout(portrait)
    return portrait


def sync_web_framebuffer() -> None:
    """竖屏时把浏览器 canvas 调到与 config.WIDTH/HEIGHT 一致，避免底部 UI 被裁切。"""
    if sys.platform not in ("emscripten", "wasi"):
        return
    try:
        import platform as pw

        w, h = config.WIDTH, config.HEIGHT
        ar = h / max(1, w)
        pw.window.run_script(
            "if (typeof config !== 'undefined') {"
            f"config.fb_width = {w};"
            f"config.fb_height = {h};"
            f"config.fb_ar = {ar};"
            "}"
        )
        cfg = pw.window.config
        for name, val in (("fb_width", w), ("fb_height", h), ("fb_ar", ar)):
            if hasattr(cfg, name):
                setattr(cfg, name, val)
        pw.window.window_resize()
    except Exception:
        pass
