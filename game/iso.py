"""斜视俯瞰（约 30–45°）坐标与绘制辅助。"""

from __future__ import annotations

import math
import random

import pygame



import config
from game.camera import camera_apply, camera_unapply



ISO_Y_SCALE = 0.58


def iso_dist(ax: float, ay: float, bx: float, by: float) -> float:
    """与画面一致的等距平面距离（用于射程、扇形判定）。"""
    dx = bx - ax
    dy = (by - ay) * ISO_Y_SCALE
    return math.hypot(dx, dy)


def iso_angle(ax: float, ay: float, bx: float, by: float) -> float:
    """与画面一致的指向角（用于扇形气流）。"""
    dx = bx - ax
    dy = (by - ay) * ISO_Y_SCALE
    return math.atan2(dy, dx)


# 与贴图匹配：地基/每层塔的视觉尺寸

FOUNDATION_RW = 52

FOUNDATION_RH = 26

TOWER_RW = 50

TOWER_RH = 24

# 每层塔中心之间的垂直间距（堆叠感，逻辑基准值）

TOWER_LAYER_STEP = 30

# 地基顶缘到第 1 层塔中心的距离

FOUNDATION_TO_TOWER1 = 20



# 塔堆超出屏幕时压缩：顶层留白、塔顶精灵/标签高度

STACK_TOP_MARGIN = 48

STACK_HEADROOM = 40

MIN_STACK_SCALE = 0.38



_stack_scale = 1.0

_stack_floors = 0





def refresh_stack_layout(

    total_floors: int,

    *,

    build_bar_h: int | None = None,

    top_margin: int = STACK_TOP_MARGIN,

) -> float:

    """根据层数计算塔堆视觉缩放（层间距 + 贴图），应在每帧绘制/点击检测前调用。"""

    global _stack_scale, _stack_floors

    _stack_floors = max(0, total_floors)

    if _stack_floors <= 0:

        _stack_scale = 1.0

        return _stack_scale



    foundation_top = config.BASE_Y - FOUNDATION_TO_TOWER1

    # 塔顶至少留出 top_margin；底部建造栏不影响向上堆叠，仅作参考

    _ = build_bar_h

    available = max(60.0, foundation_top - top_margin)

    raw_height = (_stack_floors - 1) * TOWER_LAYER_STEP + STACK_HEADROOM

    if raw_height <= available:

        _stack_scale = 1.0

    else:

        _stack_scale = max(MIN_STACK_SCALE, available / raw_height)

    return _stack_scale





def stack_scale() -> float:

    return _stack_scale





def stack_floors() -> int:

    return _stack_floors





def effective_layer_step() -> float:

    return TOWER_LAYER_STEP * _stack_scale


def stack_anchor_logical(total_floors: int) -> tuple[float, float]:
    """塔堆几何中心（逻辑屏幕坐标，未乘视角变换）。"""
    cx = float(config.BASE_X)
    if total_floors <= 0:
        return cx, float(config.BASE_Y)
    foundation_top = config.BASE_Y - FOUNDATION_TO_TOWER1
    top_cy = foundation_top - (total_floors - 1) * effective_layer_step()
    cy = (config.BASE_Y + top_cy) / 2.0
    return cx, cy


def scaled_size(base: int, minimum: int = 8) -> int:

    return max(minimum, int(base * _stack_scale))





def world_to_screen(wx: float, wy: float) -> tuple[float, float]:
    sx = wx
    sy = config.BASE_Y + (wy - config.BASE_Y) * ISO_Y_SCALE
    return camera_apply(sx, sy)





def screen_to_world(sx: float, sy: float) -> tuple[float, float]:
    """屏幕坐标 → 世界坐标（与 world_to_screen 互逆，含视角缩放）。"""
    sx, sy = camera_unapply(sx, sy)
    wx = sx
    wy = config.BASE_Y + (sy - config.BASE_Y) / ISO_Y_SCALE
    return wx, wy





def tower_screen_pos(floor: int) -> tuple[int, int]:

    """第 floor 层塔中心：与地基同轴竖直叠层（仅 Y 抬高，受 stack_scale 压缩）。"""

    cx = config.BASE_X

    foundation_top = config.BASE_Y - FOUNDATION_TO_TOWER1

    cy = foundation_top - (floor - 1) * effective_layer_step()
    cx, cy = camera_apply(cx, cy)
    return int(cx), int(cy)





def tower_world_pos(floor: int) -> tuple[float, float]:

    """该层塔的开火原点（世界坐标），与屏幕叠层位置一致。地基本身不用此函数。"""

    sx, sy = tower_screen_pos(floor)

    return screen_to_world(sx, sy)





def spawn_at_edge(angle: float | None = None) -> tuple[float, float]:

    if angle is None:

        angle = math.tau * random.random()

    x = config.BASE_X + math.cos(angle) * config.SPAWN_RADIUS

    y = config.BASE_Y + math.sin(angle) * config.SPAWN_RADIUS

    return x, y





def draw_iso_platform(

    surf: pygame.Surface,

    cx: int,

    cy: int,

    rw: int,

    rh: int,

    color: tuple,

    outline: tuple | None = None,

) -> None:

    pts = [(cx, cy - rh), (cx + rw, cy), (cx, cy + rh // 2), (cx - rw, cy)]

    pygame.draw.polygon(surf, color, pts)

    if outline:

        pygame.draw.polygon(surf, outline, pts, 2)





def draw_tower_layer_base(surf: pygame.Surface, floor: int, shadow: bool = False) -> None:

    """每层塔下方的平台描边，强化「一块叠一块」。"""

    cx, cy = tower_screen_pos(floor)

    rw = scaled_size(TOWER_RW - 2, 22)

    rh = scaled_size(TOWER_RH - 2, 10)

    if shadow:

        draw_iso_platform(surf, cx + 2, cy + 3, rw, rh, (25, 28, 38))

    col = (92, 82, 66) if floor == 1 else (76, 70, 58)
    edge = (48, 52, 62) if floor == 1 else (42, 46, 55)

    draw_iso_platform(surf, cx, cy + 2, rw, rh, col, edge)





def draw_stack_edges(surf: pygame.Surface, floors: int) -> None:

    """塔堆两侧棱线，连接地基与顶层。"""

    if floors <= 0:

        return

    bx, by = camera_apply(config.BASE_X, config.BASE_Y)

    tx, ty = tower_screen_pos(floors)

    inset = scaled_size(20, 12)

    pygame.draw.lines(surf, (58, 64, 78), False, [(bx - inset, by), (bx - inset, ty + 8)], 2)

    pygame.draw.lines(surf, (58, 64, 78), False, [(bx + inset, by), (bx + inset, ty + 8)], 2)


