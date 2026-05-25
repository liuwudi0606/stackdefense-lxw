"""兵营塔：周期生成护卫。"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

import config
from game.entities import Enemy, Guard, dist

if TYPE_CHECKING:
    from game.entities import TowerFloor
    from game.session import GameSession


def barracks_spawn_interval(tdef: dict, tower: "TowerFloor", stats) -> float:
    base = tdef.get("spawn_interval", 8.0)
    mult = 1.0 - stats.barracks_spawn_rate_mult
    mult *= max(0.55, 1.0 - 0.06 * (tower.level - 1))
    return max(2.5, base * mult)


def barracks_spawn_count(tdef: dict, tower: "TowerFloor", stats) -> int:
    n = tdef.get("spawn_count", 2) + stats.barracks_spawn_count_bonus
    n += max(0, (tower.level - 1) // 2)
    return max(1, n)


def barracks_tower_count(game: "GameSession") -> int:
    return sum(1 for t in game.towers if t.type_id == "barracks")


def barracks_max_guards(tdef: dict, stats, game: "GameSession | None" = None) -> int:
    """每座兵营独立配额；全局 Buff 加成叠在总和上。"""
    per = tdef.get("max_guards", 7)
    n = barracks_tower_count(game) if game else 1
    n = max(1, n)
    return n * per + stats.barracks_max_guards_bonus


def guard_stats_from_tower(game: "GameSession", tdef: dict, tower: "TowerFloor") -> dict:
    lv = tower.level
    hp = tdef.get("guard_hp", 55) * (1.0 + game.stats.barracks_guard_hp_mult)
    hp *= 1.0 + 0.15 * (lv - 1)
    dmg = tdef.get("guard_damage", 7) * (1.0 + game.stats.barracks_guard_damage_mult)
    dmg *= 1.0 + 0.12 * (lv - 1)
    rate = tdef.get("guard_attack_rate", 1.0) * (1.0 + game.stats.barracks_guard_rate_mult)
    rng = tdef.get("guard_range", 52)
    return {
        "hp": hp,
        "max_hp": hp,
        "damage": dmg,
        "attack_rate": rate,
        "attack_range": rng,
        "radius": tdef.get("guard_radius", 11),
        "move_speed": tdef.get("guard_speed", config.GUARD_MOVE_SPEED_DEFAULT),
        "seek_range": tdef.get("guard_seek_range", config.GUARD_SEEK_RANGE_DEFAULT),
    }


def _spawn_angle_toward_nearest_enemy(game: "GameSession", slot: int, total: int) -> float:
    """基地外围出生角：朝向最近敌人，同批多个护卫略作扇形散开。"""
    bx, by = float(config.BASE_X), float(config.BASE_Y)
    best: Enemy | None = None
    best_d = 1e9
    for e in game.enemies:
        if not e.alive:
            continue
        d = dist(bx, by, e.x, e.y)
        if d < best_d:
            best_d = d
            best = e
    if best is None:
        base_ang = random.uniform(0, 2 * math.pi)
    else:
        base_ang = math.atan2(best.y - by, best.x - bx)
    if total <= 1:
        return base_ang
    spread = config.GUARD_SPAWN_ANGLE_SPREAD
    t = (slot - (total - 1) * 0.5) / max(1, total - 1)
    return base_ang + t * spread


def _guard_spawn_pos(game: "GameSession", slot: int, total: int) -> tuple[float, float]:
    ang = _spawn_angle_toward_nearest_enemy(game, slot, total)
    r = config.GUARD_SPAWN_RING_RADIUS * random.uniform(0.92, 1.08)
    gx = config.BASE_X + math.cos(ang) * r
    gy = config.BASE_Y + math.sin(ang) * r
    return gx, gy


def spawn_guards_from_barracks(game: "GameSession", tower: "TowerFloor", tdef: dict) -> int:
    cap = barracks_max_guards(tdef, game.stats, game)
    if len(game.guards) >= cap:
        return 0
    count = barracks_spawn_count(tdef, tower, game.stats)
    count = min(count, cap - len(game.guards))
    gstat = guard_stats_from_tower(game, tdef, tower)
    spawned = 0
    for i in range(count):
        gx, gy = _guard_spawn_pos(game, i, count)
        game.guards.append(
            Guard(
                uid=game._next_guard_id(),
                x=gx,
                y=gy,
                hp=gstat["hp"],
                max_hp=gstat["max_hp"],
                damage=gstat["damage"],
                attack_range=gstat["attack_range"],
                attack_rate=gstat["attack_rate"],
                radius=gstat["radius"],
                move_speed=gstat["move_speed"],
                seek_range=gstat["seek_range"],
                spawn_x=gx,
                spawn_y=gy,
                source_floor=tower.floor,
            )
        )
        spawned += 1
    return spawned
