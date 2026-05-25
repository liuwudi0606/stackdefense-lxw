"""运行环境检测（桌面 / 浏览器 WASM）。"""

from __future__ import annotations

import sys

_pygame_ready = False


def is_web() -> bool:
    return sys.platform in ("emscripten", "wasi")


def purge_pygame_modules() -> None:
    """移除 WASM 上 pip 装坏的不完整 pygame（缺 constants 等子模块）。"""
    for name in list(sys.modules):
        if name == "pygame" or name.startswith("pygame."):
            sys.modules.pop(name, None)


def _load_pygame():
    import importlib

    try:
        pygame = importlib.import_module("pygame")
        if callable(getattr(pygame, "init", None)):
            return pygame
    except ModuleNotFoundError:
        purge_pygame_modules()
        pygame = importlib.import_module("pygame")
        if callable(getattr(pygame, "init", None)):
            return pygame
        raise

    try:
        pygame = importlib.reload(pygame)
        if callable(getattr(pygame, "init", None)):
            return pygame
    except Exception:
        pass
    purge_pygame_modules()
    return importlib.import_module("pygame")


def ensure_pygame_init() -> None:
    """网页 WASM 需在 run_main / pip 完成后再 init；勿在 main 模块顶层调用。"""
    global _pygame_ready
    if _pygame_ready:
        return
    try:
        pygame = _load_pygame()
    except ModuleNotFoundError:
        purge_pygame_modules()
        raise
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
