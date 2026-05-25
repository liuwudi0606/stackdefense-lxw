"""UI 文字居中、缩略与换行（修复中文按钮偏下/超框）。"""

from __future__ import annotations

import re

import pygame

# 换行分词：保留 【】、小数+单位、百分比增减、箭头等不被拆断
_WRAP_TOKEN = re.compile(
    r"【[^】]*】|"
    r"(?:\+?\d+(?:\.\d+)?(?:秒|人|/秒|/击))|"
    r"(?:\+?\d+(?:\.\d+)?(?:%?)(?:\s*→\s*\+?\d+(?:\.\d+)?(?:%?)?)?)|"
    r"\s+|→|·|"
    r"[\u4e00-\u9fff]+|[^\s【】→+\n]+"
)


def draw_info_icon(
    surf: pygame.Surface,
    cx: int,
    cy: int,
    font: pygame.font.Font,
    radius: int = 9,
) -> None:
    """绘制 i 信息图标（避免 ℹ 在部分中文字体显示为方框）。"""
    pygame.draw.circle(surf, (70, 85, 110), (cx, cy), radius)
    pygame.draw.circle(surf, (150, 180, 220), (cx, cy), radius, 1)
    pygame.draw.line(
        surf, (235, 245, 255), (cx, cy - radius // 2), (cx, cy + radius // 3), 2
    )
    pygame.draw.circle(surf, (235, 245, 255), (cx, cy + radius // 2), max(1, radius // 4))


def fit_render(
    font: pygame.font.Font, text: str, max_w: int, color: tuple[int, int, int]
) -> pygame.Surface:
    surf = font.render(text, True, color)
    if surf.get_width() <= max_w:
        return surf
    ell = "…"
    trimmed = text
    while trimmed and font.render(trimmed + ell, True, color).get_width() > max_w:
        trimmed = trimmed[:-1]
    return font.render((trimmed + ell) if trimmed else ell, True, color)


def blit_topleft(
    surf: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    x: int,
    y: int,
    max_w: int,
    color: tuple[int, int, int],
) -> int:
    """左上角绘制单行（可缩略），返回占用高度。"""
    img = fit_render(font, text, max_w, color)
    surf.blit(img, (x, y))
    return img.get_height()


def blit_in_rect(
    surf: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    rect: pygame.Rect,
    color: tuple[int, int, int],
    *,
    align: str = "center",
    pad: int = 6,
    clip: bool = True,
) -> None:
    inner = rect.inflate(-pad * 2, -pad * 2)
    if inner.width < 4 or inner.height < 4:
        return
    label = fit_render(font, text, inner.width, color)
    if align == "center":
        pos = label.get_rect(center=inner.center)
    elif align == "left":
        pos = label.get_rect(midleft=(inner.x, inner.centery))
    else:
        pos = label.get_rect(midright=(inner.right, inner.centery))
    if clip:
        clip_rect = rect
        parent = surf.get_clip()
        if parent.width > 0 and parent.height > 0:
            clip_rect = rect.clip(parent)
            if clip_rect.width <= 0 or clip_rect.height <= 0:
                return
        old = surf.get_clip()
        surf.set_clip(clip_rect)
        surf.blit(label, pos)
        surf.set_clip(old)
    else:
        surf.blit(label, pos)


def _tokenize_wrap(text: str) -> list[str]:
    return [t for t in _WRAP_TOKEN.findall(text) if t != ""]


def _wrap_paragraph(font: pygame.font.Font, text: str, max_w: int) -> list[str]:
    if not text:
        return []
    tokens = _tokenize_wrap(text)
    if not tokens:
        return [text]
    lines: list[str] = []
    cur = ""
    for tok in tokens:
        if tok.isspace():
            trial = cur + tok
            if cur and font.size(trial)[0] <= max_w:
                cur = trial
            continue
        trial = cur + tok
        w = font.size(trial)[0]
        if cur and w > max_w:
            lines.append(cur.rstrip())
            cur = tok.lstrip()
        else:
            cur = trial
        # 单个 token 超宽：按字拆开（极少见）
        while cur and font.size(cur)[0] > max_w and len(cur) > 1:
            split_at = max(1, len(cur) - 1)
            while split_at > 0 and font.size(cur[:split_at])[0] > max_w:
                split_at -= 1
            if split_at <= 0:
                break
            lines.append(cur[:split_at])
            cur = cur[split_at:]
    if cur.strip():
        lines.append(cur.rstrip())
    return lines or [text]


def wrap_lines(font: pygame.font.Font, text: str, max_w: int) -> list[str]:
    if not text:
        return []
    out: list[str] = []
    for part in text.split("\n"):
        if part == "":
            out.append("")
            continue
        out.extend(_wrap_paragraph(font, part, max_w))
    return out


def blit_wrapped(
    surf: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    rect: pygame.Rect,
    color: tuple[int, int, int],
    *,
    line_gap: int = 3,
    pad: int = 8,
) -> None:
    blit_wrapped_lines(surf, font, [text], rect, color, line_gap=line_gap, pad=pad)


def blit_wrapped_lines(
    surf: pygame.Surface,
    font: pygame.font.Font,
    lines: list[str],
    rect: pygame.Rect,
    color: tuple[int, int, int],
    *,
    line_gap: int = 3,
    pad: int = 8,
) -> None:
    """多行文本：每条独立换行，保留显式空行。"""
    inner = rect.inflate(-pad * 2, -pad * 2)
    y = inner.y
    old = surf.get_clip()
    surf.set_clip(rect)
    for raw in lines:
        if raw == "":
            y += max(2, font.get_linesize() // 3)
            continue
        for wl in wrap_lines(font, raw, inner.width):
            if y >= inner.bottom:
                break
            img = fit_render(font, wl, inner.width, color)
            if y + img.get_height() > inner.bottom:
                break
            surf.blit(img, (inner.x, y))
            y += img.get_height() + line_gap
    surf.set_clip(old)


def expand_lines(font: pygame.font.Font, lines: list[str], max_w: int) -> list[str]:
    out: list[str] = []
    for line in lines:
        out.extend(wrap_lines(font, line, max_w))
    return out


def expand_paragraph_lines(font: pygame.font.Font, lines: list[str], max_w: int) -> list[str]:
    """每条属性独立换行，不截断省略号；过长时仅在同一属性内折行。"""
    from game.ui_scroll import meaningful_lines

    out: list[str] = []
    for line in meaningful_lines(lines):
        wrapped = wrap_lines(font, line, max_w)
        out.extend(wrapped if wrapped else [line])
    return out


def scroll_content_height(
    font: pygame.font.Font,
    lines: list[str],
    max_w: int,
    line_gap: int = 4,
    *,
    wrap_lines: bool = True,
) -> int:
    from game.ui_scroll import meaningful_lines

    ml = meaningful_lines(lines)
    if not ml:
        return 0
    if not wrap_lines:
        expanded = expand_paragraph_lines(font, ml, max_w)
        if not expanded:
            return 0
        h = sum(font.render(ln, True, (255, 255, 255)).get_height() for ln in expanded)
        h += line_gap * max(0, len(expanded) - 1)
        return h
    expanded = expand_lines(font, ml, max_w)
    h = sum(font.render(ln, True, (255, 255, 255)).get_height() for ln in expanded)
    h += line_gap * max(0, len(expanded) - 1)
    return h


def blit_scroll_text(
    surf: pygame.Surface,
    font: pygame.font.Font,
    lines: list[str],
    content_rect: pygame.Rect,
    scroll_y: int,
    color: tuple[int, int, int],
    *,
    line_gap: int = 4,
    wrap_lines: bool = True,
) -> int:
    """绘制可滚动正文，返回最大 scroll 偏移（无溢出时为 0）。"""
    from game.ui_scroll import clamp_scroll, meaningful_lines

    inner = content_rect.inflate(-4, -4)
    ml = meaningful_lines(lines)
    total = scroll_content_height(
        font, lines, inner.width, line_gap, wrap_lines=wrap_lines
    )
    max_scroll = max(0, total - inner.height)
    scroll_y = clamp_scroll(scroll_y, max_scroll)
    y = inner.y - scroll_y
    old = surf.get_clip()
    surf.set_clip(content_rect)
    if wrap_lines:
        display = expand_lines(font, ml, inner.width)
        for line in display:
            img = font.render(line, True, color)
            lh = img.get_height()
            if y + lh > inner.y and y < inner.bottom:
                surf.blit(img, (inner.x, y))
            y += lh + line_gap
    else:
        for line in expand_paragraph_lines(font, ml, inner.width):
            img = font.render(line, True, color)
            lh = img.get_height()
            if y + lh > inner.y and y < inner.bottom:
                surf.blit(img, (inner.x, y))
            y += lh + line_gap
    surf.set_clip(old)
    return max_scroll
