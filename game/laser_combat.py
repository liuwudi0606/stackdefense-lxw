"""激光塔持续伤害与蓄能阶段计算。"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import config
from game.entities import Enemy, TowerFloor, dist

if TYPE_CHECKING:
    from game.session import GameSession


def laser_phase(tdef: dict, charge: float) -> int:
    if charge >= tdef.get("phase3_sec", 3.0):
        return 3
    if charge >= tdef.get("phase2_sec", 1.2):
        return 2
    return 1


def laser_fire_rate_factor(game: "GameSession", tower: TowerFloor | None) -> float:
    """全塔攻速与塔层升级攻速 → 激光蓄能加速（与子弹塔同源加成）。"""
    level_mult = game.tower_fire_rate_mult(tower) if tower else 1.0
    return (1.0 + game.stats.tower_fire_rate_mult) * level_mult


def laser_ramp_mult(
    tdef: dict,
    charge: float,
    laser_ramp_mult_stat: float,
    laser_cap_mult_stat: float,
    *,
    fire_rate_factor: float = 1.0,
) -> float:
    ramp_rate = (
        tdef.get("ramp_per_sec", 0.35)
        * (1.0 + laser_ramp_mult_stat)
        * max(0.1, fire_rate_factor)
    )
    cap = tdef.get("max_ramp_mult", 12.0) * (1.0 + laser_cap_mult_stat)
    extra = min(max(0.0, cap - 1.0), charge * ramp_rate)
    return 1.0 + extra


def laser_range(tdef: dict, stats) -> float:
    return tdef["range"] * (1.0 + stats.tower_range_mult + stats.laser_range_mult)


def laser_dps(game: "GameSession", tower: TowerFloor, tdef: dict) -> float:
    mult = laser_ramp_mult(
        tdef,
        tower.laser_charge,
        game.stats.laser_ramp_mult,
        game.stats.laser_cap_mult,
        fire_rate_factor=laser_fire_rate_factor(game, tower),
    )
    return (
        tdef["base_dps"]
        * mult
        * game.stats.tower_damage_factor("laser")
        * game.tower_damage_mult(tower)
    )


def laser_sweep_dps(game: "GameSession", tower: TowerFloor, tdef: dict) -> float:
    """扫射模式：固定秒伤，不随蓄能增长。"""
    return (
        tdef["base_dps"]
        * game.stats.tower_damage_factor("laser")
        * game.tower_damage_mult(tower)
    )


def laser_damage_factor(enemy: Enemy) -> float:
    return max(0.05, enemy.laser_resist * enemy.laser_vuln)


def find_laser_target(ex: float, ey: float, enemies: list[Enemy], rng: float) -> Enemy | None:
    """优先内圈；仅外圈有怪时锁定外圈，优先高血量。"""
    from game.tower_range_bands import find_target_with_far

    def pick_max_hp(cands: list[Enemy]) -> Enemy | None:
        best: Enemy | None = None
        best_hp = -1.0
        for e in cands:
            if e.hp > best_hp:
                best_hp = e.hp
                best = e
        return best

    target, _ = find_target_with_far(
        ex, ey, enemies, rng, pick_inner=pick_max_hp
    )
    return target


def target_in_laser_range(target: Enemy, rng: float) -> bool:
    from game.tower_range_bands import band_damage_mult

    return (
        band_damage_mult(config.BASE_X, config.BASE_Y, target, rng) > 0
    )


def enemies_in_laser_range(enemies: list[Enemy], rng: float) -> list[Enemy]:
    from game.tower_range_bands import band_damage_mult

    return [
        e
        for e in enemies
        if e.alive
        and band_damage_mult(config.BASE_X, config.BASE_Y, e, rng) > 0
    ]


def laser_smart_use_sweep(in_range: list[Enemy]) -> bool:
    """智能：怪多或血量分散时用扫射，否则单体蓄能。"""
    n = len(in_range)
    if n <= 1:
        return False
    if n >= 4:
        return True
    total_hp = sum(e.hp for e in in_range)
    if total_hp <= 0:
        return False
    max_hp = max(e.hp for e in in_range)
    return max_hp < total_hp * 0.55


def laser_effective_mode(game: "GameSession", tower: TowerFloor, tdef: dict) -> str:
    if not game.stats.laser_sweep_unlock:
        return "single"
    if tower.laser_auto:
        rng = laser_range(tdef, game.stats)
        in_range = enemies_in_laser_range(game.enemies, rng)
        return "sweep" if laser_smart_use_sweep(in_range) else "single"
    return "sweep" if tower.laser_mode == "sweep" else "single"


def laser_mode_label(game: "GameSession", tower: TowerFloor, tdef: dict) -> str:
    if not game.stats.laser_sweep_unlock:
        return "单体蓄能"
    if tower.laser_auto:
        mode = laser_effective_mode(game, tower, tdef)
        return "智能·扫射" if mode == "sweep" else "智能·单体"
    return "扫射" if tower.laser_mode == "sweep" else "单体蓄能"
