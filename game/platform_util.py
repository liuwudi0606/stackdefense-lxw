"""运行环境检测（桌面 / 浏览器 WASM）。"""

from __future__ import annotations

import sys

_pygame_ready = False


def is_web() -> bool:
    return sys.platform in ("emscripten", "wasi")


def ensure_pygame_init() -> None:
    """网页 WASM 版 pygame 可能没有 get_init，且需在 import 子模块前 init。"""
    global _pygame_ready
    if _pygame_ready:
        return
    import pygame

    get_init = getattr(pygame, "get_init", None)
    if callable(get_init):
        try:
            if get_init():
                _pygame_ready = True
                return
        except Exception:
            pass
    pygame.init()
    _pygame_ready = True


def web_disable_chromakey() -> None:
    """pygbag 默认 chromakey 会把首像素相近颜色变透明，易导致黑屏。"""
    if not is_web():
        return
    script = "window.chromakey = function(){};"
    for runner in (
        lambda: __import__("emscripten").run_script(script),
        lambda: __import__("platform").window.run_script(script),
    ):
        try:
            runner()
            return
        except Exception:
            continue
