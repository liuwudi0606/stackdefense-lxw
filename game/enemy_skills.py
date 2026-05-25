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


def _damage_guards_in_radius(
    game: "GameSession", cx: float, cy: float, radius: float, damage: float
) -> int:
    if game.debug_god_mode or damage <= 0:
        return 0
    n = 0
    for g in game.guards:
        if not g.alive:
            continue
        if dist(cx, cy, g.x, g.y) <= radius + g.radius:
            g.take_damage(damage)
            n += 1
    return n


def _trigger_ground_slam(game: "GameSession", enemy: "Enemy", sk: dict) -> bool:
    """震地：范围内伤基地；可选同时震伤护卫（反护卫流）。"""
    if game.debug_god_mode:
        return False
    radius = float(sk.get("radius", 120))
    cx, cy = config.BASE_X, config.BASE_Y
    if dist(enemy.x, enemy.y, cx, cy) > radius + 80:
        return False
    guard_dmg = float(sk.get("guard_damage", 0))
    if guard_dmg > 0:
        _damage_guards_in_radius(game, cx, cy, radius, guard_dmg)
    hit_base = False
    base_dmg = float(sk.get("damage", 15))
    if dist(enemy.x, enemy.y, cx, cy) <= radius and base_dmg > 0:
        game.base.take_damage(base_dmg)
        game.base_alert_timer = max(
            getattr(game, "base_alert_timer", 0.0),
            getattr(config, "GUARD_BASE_ALERT_TIMER", 3.0),
        )
        hit_base = True
    spawn_fx(
        game,
        "slam",
        cx,
        cy,
        0.45,
        radius=radius,
        seed=random.random() * 10,
    )
    if hit_base:
        game.on_sound("hurt")
    return hit_base and game.base.hp <= 0


def _trigger_shockwave(game: "GameSession", enemy: "Enemy", sk: dict) -> bool:
    """冲击波：以自身为中心，范围伤害护卫并溅射基地。"""
    if game.debug_god_mode:
        return False
    radius = float(sk.get("radius", 110))
    guard_dmg = float(sk.get("guard_damage", 16))
    base_dmg = float(sk.get("base_damage", 10))
    _damage_guards_in_radius(game, enemy.x, enemy.y, radius, guard_dmg)
    hit_base = False
    if (
        base_dmg > 0
        and dist(enemy.x, enemy.y, config.BASE_X, config.BASE_Y)
        <= radius + config.BASE_RADIUS
    ):
        game.base.take_damage(base_dmg)
        game.base_alert_timer = max(
            getattr(game, "base_alert_timer", 0.0),
            getattr(config, "GUARD_BASE_ALERT_TIMER", 3.0),
        )
        hit_base = True
    spawn_fx(
        game,
        "shockwave",
        enemy.x,
        enemy.y,
        0.42,
        radius=radius,
        seed=random.random() * 10,
    )
    if hit_base:
        game.on_sound("hurt")
    return hit_base and game.base.hp <= 0


def _trigger_guard_siege(game: "GameSession", enemy: "Enemy", sk: dict) -> bool:
    """卫压：场上护卫过多时，清剿周围护卫并直击基地。"""
    if game.debug_god_mode:
        return False
    alive = sum(1 for g in game.guards if g.alive)
    if alive < int(sk.get("min_guards", 5)):
        return False
    radius = float(sk.get("radius", 150))
    guard_dmg = float(sk.get("guard_damage", 22))
    base_dmg = float(sk.get("base_damage", 14))
    _damage_guards_in_radius(game, enemy.x, enemy.y, radius, guard_dmg)
    if base_dmg > 0:
        game.base.take_damage(base_dmg)
        game.base_alert_timer = max(
            getattr(game, "base_alert_timer", 0.0),
            getattr(config, "GUARD_BASE_ALERT_TIMER", 3.0),
        )
    spawn_fx(
        game,
        "siege",
        config.BASE_X,
        config.BASE_Y,
        0.5,
        radius=radius,
        seed=random.random() * 10,
    )
    game.on_sound("hurt")
    return game.base.hp <= 0


def attack_cleave_params(defn: dict) -> dict | None:
    raw = defn.get("attack_cleave")
    return dict(raw) if isinstance(raw, dict) else None


def apply_attack_cleave(
    game: "GameSession",
    enemy: "Enemy",
    kind: str,
    guard: "Guard | None",
) -> bool:
    """分裂斩：近战每击对周围护卫与基地造成溅射。返回是否伤及基地。"""
    if game.debug_god_mode or enemy.attack_mode != "melee":
        return False
    params = attack_cleave_params(game.enemy_defs.get(enemy.type_id, {}))
    if not params:
        return False
    radius = float(params.get("radius", 72))
    guard_mult = float(params.get("guard_damage_mult", 0.65))
    base_mult = float(params.get("base_splash_mult", 0.28))
    if guard_mult <= 0 and base_mult <= 0:
        return False

    cx, cy = enemy.x, enemy.y
    if guard and guard.alive:
        cx, cy = guard.x, guard.y
    elif kind == "base":
        cx, cy = float(config.BASE_X), float(config.BASE_Y)

    dmg = enemy.damage
    for g in game.guards:
        if not g.alive or guard is not None and g.uid == guard.uid:
            continue
        if dist(cx, cy, g.x, g.y) <= radius + g.radius:
            g.take_damage(dmg * guard_mult)

    hit_base = False
    if base_mult > 0 and dist(cx, cy, config.BASE_X, config.BASE_Y) <= radius + config.BASE_RADIUS:
        game.base.take_damage(dmg * base_mult)
        game.base_alert_timer = max(
            getattr(game, "base_alert_timer", 0.0),
            getattr(config, "GUARD_BASE_ALERT_TIMER", 3.0),
        )
        hit_base = True

    spawn_fx(
        game,
        "cleave",
        cx,
        cy,
        0.28,
        radius=radius,
        seed=random.random() * 10,
    )
    return hit_base


def _trigger_lightning(game: "GameSession", enemy: "Enemy", sk: dict) -> bool:
    """雷击：对基地脉冲伤害；可选震伤基地附近护卫。"""
    if game.debug_god_mode:
        return False
    radius = float(sk.get("radius", 9999))
    if dist(enemy.x, enemy.y, config.BASE_X, config.BASE_Y) > radius:
        return False
    guard_dmg = float(sk.get("guard_damage", 0))
    guard_radius = float(sk.get("guard_radius", 0))
    if guard_dmg > 0 and guard_radius > 0:
        _damage_guards_in_radius(
            game, config.BASE_X, config.BASE_Y, guard_radius, guard_dmg
        )
    game.base.take_damage(float(sk.get("damage", 20)))
    game.base_alert_timer = max(
        getattr(game, "base_alert_timer", 0.0),
        getattr(config, "GUARD_BASE_ALERT_TIMER", 3.0),
    )
    spawn_fx(
        game,
        "lightning",
        config.BASE_X,
        config.BASE_Y,
        0.4,
        seed=random.random() * 10,
    )
    game.on_sound("hurt")
    return game.base.hp <= 0


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
                return True
        elif sid == "shockwave":
            if _trigger_shockwave(game, enemy, sk):
                return True
        elif sid == "guard_siege":
            if _trigger_guard_siege(game, enemy, sk):
                return True
        elif sid == "lightning":
            if _trigger_lightning(game, enemy, sk):
                return True
        elif sid == "summon" or sid.startswith("summon_"):
            _trigger_summon(game, enemy, sk)

    return game.base.hp <= 0
