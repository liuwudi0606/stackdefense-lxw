"""可靠加载中文 TrueType 字体（避免 SysFont 方块乱码）。"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import config
from game.platform_util import is_web

if TYPE_CHECKING:
    import pygame

FONTS_DIR = config.ASSETS / "fonts"

# 随包分发（网页 WASM 无系统字体，必须优先使用）
BUNDLED_FONT_CANDIDATES = [
    FONTS_DIR / "NotoSansSC-Regular.otf",
    FONTS_DIR / "NotoSansSC-Regular.ttf",
]

# Windows 常见中文字体（桌面兜底）
WIN_FONT_CANDIDATES = [
    Path(r"C:\Windows\Fonts\msyh.ttc"),
    Path(r"C:\Windows\Fonts\msyhbd.ttc"),
    Path(r"C:\Windows\Fonts\simhei.ttf"),
    Path(r"C:\Windows\Fonts\simsun.ttc"),
    Path(r"C:\Windows\Fonts\simkai.ttf"),
]

_cached_path: Path | None = None
_cache: dict[tuple[int, bool], pygame.font.Font] = {}


def resolve_font_path() -> Path | None:
    global _cached_path
    if _cached_path is not None:
        return _cached_path

    search = list(BUNDLED_FONT_CANDIDATES)
    if not is_web():
        search = search + list(WIN_FONT_CANDIDATES)

    for p in search:
        if p.is_file():
            _cached_path = p
            return p
    return None


def get_font(size: int, bold: bool = False) -> "pygame.font.Font":
    import pygame

    key = (size, bold)
    if key in _cache:
        return _cache[key]
    path = resolve_font_path()
    if path:
        try:
            font = pygame.font.Font(str(path), size)
            _cache[key] = font
            return font
        except Exception:
            pass
    # 最后兜底：仍可能无法显示中文
    font = pygame.font.SysFont("arial", size)
    _cache[key] = font
    return font


def render(text: str, size: int, color: tuple[int, int, int]) -> "pygame.Surface":
    return get_font(size).render(text, True, color)
