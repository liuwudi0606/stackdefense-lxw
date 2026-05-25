"""塔射程双环（固定内外圈）+ 超过远圈后的射程加成区。"""

from __future__ import annotations

from collections.abc import Callable

import config
from game.entities import Enemy, dist, find_target


def fixed_inner_radius() -> float:
    return float(getattr(config, "TOWER_RANGE_INNER", 400))


def fixed_outer_radius() -> float:
    return float(getattr(config, "TOWER_RANGE_OUTER", 700))


def far_enemy_weight() -> float:
    return float(getattr(config, "TOWER_FAR_ENEMY_WEIGHT", 0.5))


def enemy_band(cx: float, cy: float, ex: float, ey: float, tower_rng: float) -> str:
    """inner / far(中外环50%) / beyond(超过固定远圈、在塔射程内100%) / out。"""
    d = dist(cx, cy, ex, ey)
    if d > tower_rng:
        return "out"
    if d <= fixed_inner_radius():
        return "inner"
    if d <= fixed_outer_radius():
        return "far"
    return "beyond"


def band_damage_mult(cx: float, cy: float, enemy: Enemy, tower_rng: float) -> float:
    band = enemy_band(cx, cy, enemy.x, enemy.y, tower_rng)
    if band == "inner":
        return 1.0
    if band == "far":
        return far_enemy_weight()
    if band == "beyond":
        return 1.0
    return 0.0


def count_enemies_weighted(
    cx: float,
    cy: float,
    enemies: list[Enemy],
    tower_rng: float,
) -> tuple[int, int, int, float]:
    """(固定内圈人数, 固定中外环人数, 超远圈人数, 加权有效人数)。"""
    inner_n = 0
    far_n = 0
    beyond_n = 0
    w = far_enemy_weight()
    for e in enemies:
        if not e.alive:
            continue
        band = enemy_band(cx, cy, e.x, e.y, tower_rng)
        if band == "inner":
            inner_n += 1
        elif band == "far":
            far_n += 1
        elif band == "beyond":
            beyond_n += 1
    effective = inner_n + far_n * w + beyond_n
    return inner_n, far_n, beyond_n, effective


def find_target_with_far(
    cx: float,
    cy: float,
    enemies: list[Enemy],
    tower_rng: float,
    *,
    eligible: Callable[[Enemy], bool] | None = None,
    pick_inner: Callable[[list[Enemy]], Enemy | None] | None = None,
) -> tuple[Enemy | None, float]:
    """优先内圈 → 超远圈(满额) → 中外环(50%)。"""

    def ok(e: Enemy) -> bool:
        if not e.alive:
            return False
        return eligible(e) if eligible else True

    def in_band_name(name: str) -> list[Enemy]:
        return [
            e
            for e in enemies
            if ok(e) and enemy_band(cx, cy, e.x, e.y, tower_rng) == name
        ]

    def pick(cands: list[Enemy], search_rng: float) -> Enemy | None:
        if not cands:
            return None
        if pick_inner:
            return pick_inner(cands)
        return find_target(cx, cy, cands, search_rng, eligible=eligible)

    for band_name, mult in (("inner", 1.0), ("beyond", 1.0), ("far", far_enemy_weight())):
        cands = in_band_name(band_name)
        t = pick(cands, tower_rng)
        if t:
            return t, mult
    return None, 1.0


# 兼容旧引用：远圈 = 固定外圈半径
def far_range_extent(_inner: float | None = None) -> float:
    return fixed_outer_radius()
