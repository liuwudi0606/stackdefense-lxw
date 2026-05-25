"""运行环境检测（桌面 / 浏览器 WASM）。"""

from __future__ import annotations

import sys


def is_web() -> bool:
    return sys.platform in ("emscripten", "wasi")


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
