"""可滚动文本区：范围限制、滚动条绘制与拖拽。"""

from __future__ import annotations

from dataclasses import dataclass

import pygame


def meaningful_lines(lines: list[str]) -> list[str]:
    return [ln for ln in lines if ln and str(ln).strip()]


def clamp_scroll(scroll_y: int, max_scroll: int) -> int:
    return max(0, min(max(0, max_scroll), scroll_y))


def scroll_max(content_height: int, viewport_height: int) -> int:
    return max(0, content_height - viewport_height)


def scroll_track_rect(content: pygame.Rect, *, width: int = 6, gap: int = 4) -> pygame.Rect:
    return pygame.Rect(content.right + gap, content.y, width, content.height)


def scroll_thumb_height(viewport_height: int, max_scroll: int, *, min_h: int = 16) -> int:
    if max_scroll <= 0:
        return 0
    return max(min_h, int(viewport_height * viewport_height / (viewport_height + max_scroll)))


def scroll_thumb_rect(
    content: pygame.Rect, scroll_y: int, max_scroll: int, *, width: int = 6, gap: int = 4
) -> pygame.Rect:
    track = scroll_track_rect(content, width=width, gap=gap)
    th = scroll_thumb_height(content.height, max_scroll)
    if max_scroll <= 0 or th <= 0:
        return pygame.Rect(track.x, track.y, width, 0)
    ratio = scroll_y / max_scroll
    ty = track.y + int((track.height - th) * ratio)
    return pygame.Rect(track.x, ty, width, th)


def scroll_y_from_thumb_top(
    content: pygame.Rect, thumb_top: int, max_scroll: int, *, width: int = 6, gap: int = 4
) -> int:
    track = scroll_track_rect(content, width=width, gap=gap)
    th = scroll_thumb_height(content.height, max_scroll)
    travel = max(1, track.height - th)
    rel = max(0, min(travel, thumb_top - track.y))
    return int(rel / travel * max_scroll)


def draw_scrollbar(
    surf: pygame.Surface,
    content: pygame.Rect,
    scroll_y: int,
    max_scroll: int,
    *,
    width: int = 6,
    gap: int = 4,
    track_color=(45, 48, 58),
    thumb_color=(120, 140, 180),
) -> tuple[pygame.Rect, pygame.Rect]:
    """绘制滚动条，返回 (track, thumb)。"""
    track = scroll_track_rect(content, width=width, gap=gap)
    thumb = scroll_thumb_rect(content, scroll_y, max_scroll, width=width, gap=gap)
    if max_scroll <= 0:
        return track, thumb
    pygame.draw.rect(surf, track_color, track, border_radius=3)
    if thumb.height > 0:
        pygame.draw.rect(surf, thumb_color, thumb, border_radius=3)
    return track, thumb


def hit_scrollbar(
    mx: int,
    my: int,
    content: pygame.Rect,
    scroll_y: int,
    max_scroll: int,
    *,
    width: int = 6,
    gap: int = 4,
) -> str | None:
    """命中 track 或 thumb，返回 'track' | 'thumb' | None。"""
    if max_scroll <= 0:
        return None
    track = scroll_track_rect(content, width=width, gap=gap)
    thumb = scroll_thumb_rect(content, scroll_y, max_scroll, width=width, gap=gap)
    if thumb.height > 0 and thumb.collidepoint(mx, my):
        return "thumb"
    if track.collidepoint(mx, my):
        return "track"
    return None


@dataclass
class ScrollDragState:
    kind: str
    grab_offset_y: int = 0
    drag_mode: str = "thumb"
    start_y: int = 0
    start_scroll: int = 0


def start_scroll_drag(kind: str, mx: int, my: int, thumb: pygame.Rect) -> ScrollDragState:
    return ScrollDragState(kind=kind, grab_offset_y=my - thumb.y, drag_mode="thumb")


def start_content_scroll_drag(kind: str, my: int, scroll_y: int) -> ScrollDragState:
    return ScrollDragState(
        kind=kind,
        drag_mode="content",
        start_y=my,
        start_scroll=scroll_y,
    )


def drag_content_scroll_y(my: int, state: ScrollDragState, max_scroll: int) -> int:
    return clamp_scroll(state.start_scroll + state.start_y - my, max_scroll)


def drag_scroll_y(
    my: int,
    state: ScrollDragState,
    content: pygame.Rect,
    max_scroll: int,
    *,
    width: int = 6,
    gap: int = 4,
) -> int:
    thumb_top = my - state.grab_offset_y
    return scroll_y_from_thumb_top(
        content, thumb_top, max_scroll, width=width, gap=gap
    )
