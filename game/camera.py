"""游戏区域视角缩放（滚轮），以屏幕点为缩放锚点。"""

from __future__ import annotations

import config

_view_zoom = 1.0
_view_pan_x = 0.0
_view_pan_y = 0.0


def view_zoom() -> float:
    return _view_zoom


def reset_view() -> None:
    global _view_zoom, _view_pan_x, _view_pan_y
    _view_zoom = config.VIEW_ZOOM_DEFAULT
    _view_pan_x = 0.0
    _view_pan_y = 0.0


def _clamp_zoom(z: float) -> float:
    return max(config.VIEW_ZOOM_MIN, min(config.VIEW_ZOOM_MAX, z))


def camera_apply(sx: float, sy: float) -> tuple[float, float]:
    """逻辑屏幕坐标 → 缩放后的绘制坐标。"""
    z = _view_zoom
    return (
        config.BASE_X + _view_pan_x + (sx - config.BASE_X) * z,
        config.BASE_Y + _view_pan_y + (sy - config.BASE_Y) * z,
    )


def camera_unapply(sx: float, sy: float) -> tuple[float, float]:
    """缩放后坐标 → 逻辑屏幕坐标（用于点击反算）。"""
    z = _view_zoom
    if z < 1e-6:
        z = config.VIEW_ZOOM_DEFAULT
    return (
        config.BASE_X + (sx - config.BASE_X - _view_pan_x) / z,
        config.BASE_Y + (sy - config.BASE_Y - _view_pan_y) / z,
    )


def base_screen() -> tuple[float, float]:
    return camera_apply(config.BASE_X, config.BASE_Y)


def view_state_dict() -> dict:
    return {"zoom": _view_zoom, "pan_x": _view_pan_x, "pan_y": _view_pan_y}


def load_view_state(data: dict | None) -> None:
    global _view_zoom, _view_pan_x, _view_pan_y
    if not data:
        reset_view()
        return
    _view_zoom = _clamp_zoom(float(data.get("zoom", config.VIEW_ZOOM_DEFAULT)))
    _view_pan_x = float(data.get("pan_x", 0.0))
    _view_pan_y = float(data.get("pan_y", 0.0))


def apply_wheel_zoom(delta_y: int, anchor_sx: float, anchor_sy: float) -> float:
    """在游戏区域内滚轮缩放，锚点为当前鼠标逻辑坐标。返回新倍率。"""
    global _view_zoom, _view_pan_x, _view_pan_y
    if delta_y == 0:
        return _view_zoom
    delta_y = max(-4, min(4, int(delta_y)))
    uncam_x, uncam_y = camera_unapply(anchor_sx, anchor_sy)
    factor = config.VIEW_ZOOM_STEP ** delta_y
    new_z = _clamp_zoom(_view_zoom * factor)
    if abs(new_z - _view_zoom) < 1e-6:
        return _view_zoom
    _view_zoom = new_z
    _view_pan_x = anchor_sx - config.BASE_X - (uncam_x - config.BASE_X) * new_z
    _view_pan_y = anchor_sy - config.BASE_Y - (uncam_y - config.BASE_Y) * new_z
    return _view_zoom
