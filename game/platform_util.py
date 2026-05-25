"""运行环境检测（桌面 / 浏览器 WASM）。"""

from __future__ import annotations

import sys

_pygame_ready = False


def is_web() -> bool:
    return sys.platform in ("emscripten", "wasi")


def _load_pygame():
    import importlib
    import sys

    import pygame

    if callable(getattr(pygame, "init", None)):
        return pygame
    try:
        pygame = importlib.reload(pygame)
    except Exception:
        pass
    if callable(getattr(pygame, "init", None)):
        return pygame
    sys.modules.pop("pygame", None)
    import pygame

    return pygame


def ensure_pygame_init() -> None:
    """网页 WASM 需在 run_main / pip 完成后再 init；勿在 main 模块顶层调用。"""
    global _pygame_ready
    if _pygame_ready:
        return
    pygame = _load_pygame()
    init_fn = getattr(pygame, "init", None)
    if not callable(init_fn):
        return

    get_init = getattr(pygame, "get_init", None)
    if callable(get_init):
        try:
            if get_init():
                _pygame_ready = True
                return
        except Exception:
            pass
    init_fn()
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
