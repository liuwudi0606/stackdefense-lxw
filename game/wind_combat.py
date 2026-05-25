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
    deg = tdef.get("fan_angle_deg", 40) + tdef.get("fan_angle_per_level", 7) * (
        tower.level - 1
    )
    deg *= 1.0 + wind_fan_mult
    return math.radians(max(12, min(120, deg))) / 2


def wind_knockback(tdef: dict, tower: "TowerFloor", wind_knockback_mult: float) -> float:
    base = tdef.get("knockback", 32)
    level_scale = 1.0 + 0.12 * (tower.level - 1)
    return base * level_scale * (1.0 + wind_knockback_mult)


def wind_fire_rate(tdef: dict, tower: "TowerFloor", stats) -> float:
    rate = tdef["fire_rate"] * (1.0 + stats.tower_fire_rate_mult + stats.wind_rate_mult)
    rate *= 1.0 + 0.1 * (tower.level - 1)
    return max(0.15, rate)


def wind_range(tdef: dict, stats) -> float:
    return tdef["range"] * (1.0 + stats.tower_range_mult + stats.wind_range_mult)


def enemies_in_fan(
    ox: float,
    oy: float,
    aim_rad: float,
    rng: float,
    half_angle: float,
    enemies: list[Enemy],
) -> list[Enemy]:
    hit: list[Enemy] = []
    for e in enemies:
        if not e.alive:
            continue
        d = iso_dist(ox, oy, e.x, e.y)
        if d > rng + e.radius or d < 8:
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
        e.knockback_vx = (dx / d) * speed * kb
        e.knockback_vy = (dy / d) * speed * kb
        e.knockback_time = duration
        n += 1
    return n


def wind_aim_target(game: "GameSession", rng: float) -> Enemy | None:
    ox, oy = config.BASE_X, config.BASE_Y
    best: Enemy | None = None
    best_d = rng
    for e in game.enemies:
        if not e.alive:
            continue
        d = iso_dist(ox, oy, e.x, e.y)
        if d <= rng and d < best_d:
            best_d = d
            best = e
    return best
