"""游戏区域视角：缩放、平移；锚点为塔堆几何中心（非仅地基）。"""

from __future__ import annotations

import config

_view_zoom = 1.0
_view_pan_x = 0.0
_view_pan_y = 0.0
_view_anchor_x = float(config.BASE_X)
_view_anchor_y = float(config.BASE_Y)
_drag_last: tuple[int, int] | None = None

# 塔堆中心默认落在屏幕略偏上，为底部建造栏留空
_FOCUS_SCREEN_X = 0.5
_FOCUS_SCREEN_Y = 0.46


def view_zoom() -> float:
    return _view_zoom


def view_anchor() -> tuple[float, float]:
    return _view_anchor_x, _view_anchor_y


def reset_view() -> None:
    global _view_zoom, _view_pan_x, _view_pan_y, _view_anchor_x, _view_anchor_y, _drag_last
    _view_zoom = config.VIEW_ZOOM_DEFAULT
    _view_pan_x = 0.0
    _view_pan_y = 0.0
    _view_anchor_x = float(config.BASE_X)
    _view_anchor_y = float(config.BASE_Y)
    _drag_last = None


def _clamp_zoom(z: float) -> float:
    return max(config.VIEW_ZOOM_MIN, min(config.VIEW_ZOOM_MAX, z))


def _focus_screen() -> tuple[float, float]:
    return config.WIDTH * _FOCUS_SCREEN_X, config.HEIGHT * _FOCUS_SCREEN_Y


def camera_apply(sx: float, sy: float) -> tuple[float, float]:
    """逻辑屏幕坐标 → 缩放后的绘制坐标。"""
    ax, ay = _view_anchor_x, _view_anchor_y
    z = _view_zoom
    return (
        ax + _view_pan_x + (sx - ax) * z,
        ay + _view_pan_y + (sy - ay) * z,
    )


def camera_unapply(sx: float, sy: float) -> tuple[float, float]:
    """缩放后坐标 → 逻辑屏幕坐标（用于点击反算）。"""
    ax, ay = _view_anchor_x, _view_anchor_y
    z = _view_zoom
    if z < 1e-6:
        z = config.VIEW_ZOOM_DEFAULT
    return (
        ax + (sx - ax - _view_pan_x) / z,
        ay + (sy - ay - _view_pan_y) / z,
    )


def base_screen() -> tuple[float, float]:
    return camera_apply(config.BASE_X, config.BASE_Y)


def focus_on_stack(total_floors: int) -> None:
    """以整座塔楼（地基+各层）的几何中心为视角锚点，并置于默认屏幕位置。"""
    global _view_anchor_x, _view_anchor_y, _view_pan_x, _view_pan_y
    from game.iso import stack_anchor_logical

    ax, ay = stack_anchor_logical(total_floors)
    tx, ty = _focus_screen()
    _view_anchor_x, _view_anchor_y = ax, ay
    _view_pan_x = tx - ax
    _view_pan_y = ty - ay


def view_state_dict() -> dict:
    return {
        "zoom": _view_zoom,
        "pan_x": _view_pan_x,
        "pan_y": _view_pan_y,
        "anchor_x": _view_anchor_x,
        "anchor_y": _view_anchor_y,
    }


def load_view_state(data: dict | None) -> None:
    global _view_zoom, _view_pan_x, _view_pan_y, _view_anchor_x, _view_anchor_y, _drag_last
    if not data:
        reset_view()
        return
    _view_zoom = _clamp_zoom(float(data.get("zoom", config.VIEW_ZOOM_DEFAULT)))
    _view_pan_x = float(data.get("pan_x", 0.0))
    _view_pan_y = float(data.get("pan_y", 0.0))
    _view_anchor_x = float(data.get("anchor_x", config.BASE_X))
    _view_anchor_y = float(data.get("anchor_y", config.BASE_Y))
    _drag_last = None


def apply_wheel_zoom(delta_y: int, anchor_sx: float, anchor_sy: float) -> float:
    """在游戏区域内滚轮缩放，锚点为当前鼠标逻辑坐标。返回新倍率。"""
    global _view_zoom, _view_pan_x, _view_pan_y
    if delta_y == 0:
        return _view_zoom
    delta_y = max(-4, min(4, int(delta_y)))
    ax, ay = _view_anchor_x, _view_anchor_y
    uncam_x, uncam_y = camera_unapply(anchor_sx, anchor_sy)
    factor = config.VIEW_ZOOM_STEP ** delta_y
    new_z = _clamp_zoom(_view_zoom * factor)
    if abs(new_z - _view_zoom) < 1e-6:
        return _view_zoom
    _view_zoom = new_z
    _view_pan_x = anchor_sx - ax - (uncam_x - ax) * new_z
    _view_pan_y = anchor_sy - ay - (uncam_y - ay) * new_z
    return _view_zoom


def end_drag_pan() -> None:
    global _drag_last
    _drag_last = None


def update_drag_pan(mx: int, my: int) -> bool:
    """空白区域按住拖动 → 平移地图。返回 True 表示正在处理拖移。"""
    global _view_pan_x, _view_pan_y, _drag_last
    if _drag_last is None:
        _drag_last = (mx, my)
        return True
    dx = mx - _drag_last[0]
    dy = my - _drag_last[1]
    _drag_last = (mx, my)
    if dx or dy:
        _view_pan_x += dx
        _view_pan_y += dy
    return True
