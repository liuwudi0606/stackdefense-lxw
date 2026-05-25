"""敌人 / Boss 主动技能（数据驱动，见 data/enemies.json skills 字段）。"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

import config
from game.buff_fx import spawn_fx
from game.entities import dist
if TYPE_CHECKING:
    from game.entities import Enemy
    from game.session import GameSession


def init_enemy_skills(enemy: "Enemy", defn: dict) -> None:
    enemy.skill_cds.clear()
    enemy.skill_flags.clear()
    for sk in defn.get("skills") or []:
        sid = sk.get("id")
        if not sid:
            continue
        interval = float(sk.get("interval", 8.0))
        enemy.skill_cds[sid] = interval * random.uniform(0.35, 0.75)


def _skill_list(defn: dict) -> list[dict]:
    raw = defn.get("skills")
    return list(raw) if raw else []


def _skill(defn: dict, skill_id: str) -> dict | None:
    for sk in _skill_list(defn):
        if sk.get("id") == skill_id:
            return sk
    return None


def _tick_cd(enemy: "Enemy", skill_id: str, dt: float) -> float:
    cd = enemy.skill_cds.get(skill_id, 0.0) - dt
    enemy.skill_cds[skill_id] = cd
    return cd


def _trigger_enrage(enemy: "Enemy", sk: dict) -> None:
    if enemy.skill_flags.get("enraged"):
        return
    hp_ratio = enemy.hp / max(1.0, enemy.max_hp)
    if hp_ratio > float(sk.get("hp_below", 0.5)):
        return
    enemy.skill_flags["enraged"] = True
    enemy.damage *= float(sk.get("damage_mult", 1.3))
    enemy.speed *= float(sk.get("speed_mult", 1.2))
    enemy.attack_rate *= float(sk.get("rate_mult", 1.0))


def _trigger_ground_slam(game: "GameSession", enemy: "Enemy", sk: dict) -> bool:
    """震地：对基地造成范围伤害。返回是否对基地造成伤害。"""
    if game.debug_god_mode:
        return False
    radius = float(sk.get("radius", 120))
    if dist(enemy.x, enemy.y, config.BASE_X, config.BASE_Y) > radius:
        return False
    dmg = float(sk.get("damage", 15))
    game.base.take_damage(dmg)
    spawn_fx(
        game,
        "slam",
        config.BASE_X,
        config.BASE_Y,
        0.45,
        radius=radius,
        seed=random.random() * 10,
    )
    game.on_sound("hurt")
    return True


def _trigger_lightning(game: "GameSession", enemy: "Enemy", sk: dict) -> bool:
    """雷击：超远程对基地脉冲伤害（不要求贴近）。"""
    if game.debug_god_mode:
        return False
    radius = float(sk.get("radius", 9999))
    if dist(enemy.x, enemy.y, config.BASE_X, config.BASE_Y) > radius:
        return False
    game.base.take_damage(float(sk.get("damage", 20)))
    spawn_fx(
        game,
        "lightning",
        config.BASE_X,
        config.BASE_Y,
        0.4,
        seed=random.random() * 10,
    )
    game.on_sound("hurt")
    return True


def _trigger_summon(game: "GameSession", enemy: "Enemy", sk: dict) -> None:
    if len(game.enemies) >= int(sk.get("cap", 95)):
        return
    tid = sk.get("spawn", "grunt")
    if tid not in game.enemy_defs:
        return
    count = int(sk.get("count", 2))
    spread = float(sk.get("spread", 55))
    for _ in range(count):
        ang = random.uniform(0, math.tau)
        r = random.uniform(12, spread)
        x = enemy.x + math.cos(ang) * r
        y = enemy.y + math.sin(ang) * r
        game.spawn_enemy(tid, x, y)
    spawn_fx(game, "exp", enemy.x, enemy.y, 0.35, seed=random.random())


def _trigger_regen(enemy: "Enemy", sk: dict, dt: float) -> None:
    if enemy.hp >= enemy.max_hp:
        return
    rate = float(sk.get("hp_per_sec_ratio", 0.006))
    enemy.hp = min(enemy.max_hp, enemy.hp + enemy.max_hp * rate * dt)


def tick_enemy_skills(game: "GameSession", enemy: "Enemy", dt: float) -> bool:
    """
    处理技能冷却与触发。返回 True 表示基地已被技能摧毁。
    """
    if not enemy.alive:
        return False

    defn = game.enemy_defs.get(enemy.type_id, {})
    for sk in _skill_list(defn):
        sid = sk.get("id")
        if not sid:
            continue

        if sid == "enrage":
            _trigger_enrage(enemy, sk)
            continue

        if sid == "regen":
            _trigger_regen(enemy, sk, dt)
            continue

        interval = float(sk.get("interval", 0))
        if interval <= 0:
            continue

        cd = _tick_cd(enemy, sid, dt)
        if cd > 0:
            continue

        enemy.skill_cds[sid] = interval

        if sid == "ground_slam":
            if _trigger_ground_slam(game, enemy, sk):
                return game.base.hp <= 0
        elif sid == "lightning":
            if _trigger_lightning(game, enemy, sk):
                return game.base.hp <= 0
        elif sid == "summon" or sid.startswith("summon_"):
            _trigger_summon(game, enemy, sk)

    return game.base.hp <= 0
