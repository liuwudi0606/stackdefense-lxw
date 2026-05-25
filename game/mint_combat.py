"""钱塔：周期根据射程内敌人数量产金（不造成伤害）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

import config
from game.entities import dist

if TYPE_CHECKING:
    from game.entities import Enemy, TowerFloor
    from game.session import GameSession


def mint_range(tdef: dict, stats) -> float:
    return float(tdef["range"]) * (1.0 + stats.tower_range_mult + stats.mint_range_mult)


def mint_interval(tdef: dict, tower: "TowerFloor", stats) -> float:
    base = float(tdef.get("mint_interval", 5.0))
    mult = max(0.4, 1.0 - stats.mint_rate_mult)
    level_bonus = max(0.85, 1.0 - 0.06 * (tower.level - 1))
    return base * mult * level_bonus


def count_enemies_in_mint_range(game: "GameSession", rng: float) -> int:
    ex, ey = config.BASE_X, config.BASE_Y
    return sum(
        1 for e in game.enemies if e.alive and dist(ex, ey, e.x, e.y) <= rng
    )


def calc_mint_gold(game: "GameSession", tdef: dict, tower: "TowerFloor", enemy_count: int) -> int:
    base = float(tdef.get("mint_base", 1))
    per = float(tdef.get("mint_per_enemy", 4)) * (1.0 + game.stats.mint_yield_mult)
    cap = float(tdef.get("mint_cap", 48)) * (1.0 + game.stats.mint_cap_mult)
    stack = game.tower_type_stack_mult(tower)
    raw = (base + per * enemy_count) * stack
    raw = min(cap, raw)
    if enemy_count <= 0:
        raw *= float(tdef.get("mint_empty_factor", 0.15))
    return max(0, int(raw * (1.0 + game.stats.gold_mult)))


def apply_mint_tick(
    game: "GameSession", tower: "TowerFloor", tdef: dict, enemy_count: int
) -> int:
    gold = calc_mint_gold(game, tdef, tower, enemy_count)
    if gold > 0:
        game.gold += gold
    return gold
