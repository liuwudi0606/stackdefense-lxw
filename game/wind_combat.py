"""风塔扇形击退计算。"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import config
from game.entities import Enemy
from game.iso import iso_angle, iso_dist

if TYPE_CHECKING:
    from game.entities import TowerFloor
    from game.session import GameSession


def _angle_diff(a: float, b: float) -> float:
    d = (a - b + math.pi) % (2 * math.pi) - math.pi
    return d


def wind_fan_half_angle_rad(tdef: dict, tower: "TowerFloor", wind_fan_mult: float) -> float:
    deg = float(tdef.get("fan_angle_deg", 40))
    deg *= 1.0 + wind_fan_mult
    return math.radians(max(12, min(120, deg))) / 2


def wind_knockback(tdef: dict, tower: "TowerFloor", wind_knockback_mult: float) -> float:
    base = float(tdef.get("knockback", 32))
    per_lv = float(tdef.get("knockback_per_level", 0.18))
    level_scale = 1.0 + per_lv * (tower.level - 1)
    return base * level_scale * (1.0 + wind_knockback_mult)


def wind_fire_rate(
    tdef: dict, tower: "TowerFloor | None" = None, stats=None
) -> float:
    """风塔固定每秒 1 次，不受全局攻速与 wind_rate 增益影响。"""
    return float(getattr(config, "WIND_FIRE_RATE", 1.0))


def wind_range(
    tdef: dict, stats, tower: "TowerFloor | None" = None
) -> float:
    r = tdef["range"] * (1.0 + stats.tower_range_mult + stats.wind_range_mult)
    if tower is not None:
        per_lv = float(tdef.get("range_per_level", 0.11))
        r *= 1.0 + per_lv * (tower.level - 1)
    return r


def enemies_in_fan(
    ox: float,
    oy: float,
    aim_rad: float,
    inner_rng: float,
    half_angle: float,
    enemies: list[Enemy],
) -> list[Enemy]:
    hit: list[Enemy] = []
    for e in enemies:
        if not e.alive:
            continue
        d = iso_dist(ox, oy, e.x, e.y)
        if d > inner_rng + e.radius or d < 8:
            continue
        ang = iso_angle(ox, oy, e.x, e.y)
        if abs(_angle_diff(ang, aim_rad)) <= half_angle:
            hit.append(e)
    return hit


def apply_wind_knockback(
    enemies: list[Enemy],
    ox: float,
    oy: float,
    force: float,
    *,
    inner_rng: float | None = None,
) -> int:
    """从原点向外击退（线性滑动，非瞬移），返回命中数。"""
    duration = max(0.08, config.WIND_KNOCKBACK_DURATION)
    speed = force / duration
    n = 0
    for e in enemies:
        if not e.alive:
            continue
        dx = e.x - ox
        dy = e.y - oy
        d = math.hypot(dx, dy)
        if d < 1e-3:
            dx = e.x - config.BASE_X
            dy = e.y - config.BASE_Y
            d = math.hypot(dx, dy)
        if d < 1e-3:
            continue
        kb = max(0.0, min(1.0, e.wind_resist))
        if kb <= 0:
            continue
        band_mult = 1.0
        if inner_rng is not None:
            from game.tower_range_bands import band_damage_mult

            band_mult = band_damage_mult(ox, oy, e, inner_rng)
            if band_mult <= 0:
                continue
        e.knockback_vx = (dx / d) * speed * kb * band_mult
        e.knockback_vy = (dy / d) * speed * kb * band_mult
        e.knockback_time = duration
        n += 1
    return n


def wind_aim_target(game: "GameSession", inner_rng: float) -> Enemy | None:
    from game.tower_range_bands import find_target_with_far

    ox, oy = config.BASE_X, config.BASE_Y
    target, _ = find_target_with_far(ox, oy, game.enemies, inner_rng)
    return target
