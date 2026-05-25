"""敌人/护卫与基地的目标选择与战斗。"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import config
from game.entities import Enemy, Guard, dist, find_target

if TYPE_CHECKING:
    from game.session import GameSession


def _stop_distance(enemy: Enemy, target_radius: float) -> float:
    if enemy.attack_mode == "ranged":
        return max(40.0, enemy.attack_range)
    return target_radius + enemy.radius * 0.7 + config.ENEMY_MELEE_PADDING


def _contact_range(enemy: Enemy, guard: Guard) -> float:
    return enemy.radius + guard.radius + config.ENEMY_MELEE_PADDING


def _guard_by_uid(game: "GameSession", uid: int | None) -> Guard | None:
    if uid is None:
        return None
    for g in game.guards:
        if g.alive and g.uid == uid:
            return g
    return None


def _guards_touching(enemy: Enemy, guards: list[Guard]) -> list[Guard]:
    hit: list[Guard] = []
    for g in guards:
        if not g.alive:
            continue
        if dist(enemy.x, enemy.y, g.x, g.y) <= _contact_range(enemy, g):
            hit.append(g)
    return hit


def enemy_aggro_guard(game: "GameSession", enemy: Enemy, guard: Guard) -> None:
    """护卫造成伤害后，敌人转而攻击该护卫。"""
    if guard.alive:
        enemy.aggro_guard_uid = guard.uid


def _clear_stale_aggro(game: "GameSession", enemy: Enemy) -> None:
    if enemy.aggro_guard_uid is None:
        return
    g = _guard_by_uid(game, enemy.aggro_guard_uid)
    if g is None:
        enemy.aggro_guard_uid = None
        return
    if dist(enemy.x, enemy.y, g.x, g.y) > config.ENEMY_AGGRO_DROP_RANGE:
        enemy.aggro_guard_uid = None


def pick_enemy_target(game: "GameSession", enemy: Enemy) -> tuple[str, float, float, Guard | None]:
    """默认冲向基地；仅护卫贴身阻挡或遭护卫攻击后才以护卫为目标。"""
    _clear_stale_aggro(game, enemy)

    aggro = _guard_by_uid(game, enemy.aggro_guard_uid)
    if aggro is not None:
        return "guard", aggro.x, aggro.y, aggro

    touching = _guards_touching(enemy, game.guards)
    if touching:
        g = min(touching, key=lambda gr: dist(enemy.x, enemy.y, gr.x, gr.y))
        return "guard", g.x, g.y, g

    return "base", float(config.BASE_X), float(config.BASE_Y), None


def _move_toward(enemy: Enemy, tx: float, ty: float, dt: float, aura_slow: float) -> None:
    spd = enemy.speed * enemy.slow_factor
    if aura_slow > 0 and dist(enemy.x, enemy.y, config.BASE_X, config.BASE_Y) < config.BASE_AURA_RADIUS:
        enemy.in_base_aura = True
        spd *= 1.0 - aura_slow
    d = dist(enemy.x, enemy.y, tx, ty)
    if d <= 0:
        return
    step = spd * dt
    if step >= d:
        enemy.x, enemy.y = tx, ty
    else:
        enemy.x += (tx - enemy.x) / d * step
        enemy.y += (ty - enemy.y) / d * step


def _apply_enemy_hit(
    game: "GameSession", enemy: Enemy, kind: str, guard: Guard | None
) -> bool:
    """造成伤害，返回是否对基地造成伤害（用于音效）。"""
    if game.debug_god_mode:
        return False
    dmg = enemy.damage
    if kind == "guard" and guard and guard.alive:
        guard.take_damage(dmg)
        return False
    if kind == "base":
        game.base.take_damage(dmg)
        game.base_alert_timer = max(
            getattr(game, "base_alert_timer", 0.0),
            getattr(config, "GUARD_BASE_ALERT_TIMER", 3.0),
        )
        if game.stats.base_thorns > 0:
            enemy.take_damage(float(game.stats.base_thorns))
            from game.buff_fx import on_base_thorns_hit

            on_base_thorns_hit(game, enemy.x, enemy.y)
        return True
    return False


def _update_enemy_knockback(enemy: Enemy, dt: float) -> bool:
    """击退中仅沿击退速度位移。返回 True 表示本帧仍在击退。"""
    if enemy.knockback_time <= 0:
        enemy.knockback_vx = 0.0
        enemy.knockback_vy = 0.0
        return False
    enemy.x += enemy.knockback_vx * dt
    enemy.y += enemy.knockback_vy * dt
    enemy.knockback_time = max(0.0, enemy.knockback_time - dt)
    if enemy.knockback_time <= 0:
        enemy.knockback_vx = 0.0
        enemy.knockback_vy = 0.0
        return False
    return True


def update_enemy_combat(game: "GameSession", enemy: Enemy, dt: float) -> bool:
    """更新单个敌人移动与攻击。基地被击破时返回 True。"""
    if not enemy.alive:
        return False

    if _update_enemy_knockback(enemy, dt):
        return game.base.hp <= 0

    enemy.in_base_aura = False
    enemy.frost_phase += dt * 6.0
    if enemy.slow_timer > 0:
        enemy.slow_timer -= dt
        if enemy.slow_timer <= 0:
            enemy.slow_factor = 1.0

    from game.enemy_skills import tick_enemy_skills

    if tick_enemy_skills(game, enemy, dt):
        return True

    kind, tx, ty, guard = pick_enemy_target(game, enemy)
    target_r = guard.radius if guard else config.BASE_RADIUS
    stop = _stop_distance(enemy, target_r)
    d = dist(enemy.x, enemy.y, tx, ty)

    if d > stop:
        _move_toward(enemy, tx, ty, dt, game.stats.base_aura_slow)
        return game.base.hp <= 0

    enemy.attack_cd -= dt
    if enemy.attack_cd > 0:
        return game.base.hp <= 0

    enemy.attack_cd = 1.0 / max(0.15, enemy.attack_rate)
    hit_base = _apply_enemy_hit(game, enemy, kind, guard)
    if hit_base:
        game.on_sound("hurt")
    return game.base.hp <= 0


def _move_guard_toward(guard: Guard, tx: float, ty: float, dt: float) -> None:
    d = dist(guard.x, guard.y, tx, ty)
    if d <= 0:
        return
    step = guard.move_speed * dt
    if step >= d:
        guard.x, guard.y = tx, ty
    else:
        guard.x += (tx - guard.x) / d * step
        guard.y += (ty - guard.y) / d * step


def _guard_home_pos(guard: Guard) -> tuple[float, float]:
    """护卫待命点（兵营生成位置，基地外围）。"""
    if guard.spawn_x != 0.0 or guard.spawn_y != 0.0:
        return guard.spawn_x, guard.spawn_y
    ang = (guard.uid * 0.73) % (2 * math.pi)
    r = config.GUARD_SPAWN_RING_RADIUS
    return (
        config.BASE_X + math.cos(ang) * r,
        config.BASE_Y + math.sin(ang) * r,
    )


def _any_alive_enemy(game: "GameSession") -> bool:
    return any(e.alive for e in game.enemies)


def _enemy_targets_base(game: "GameSession", enemy: Enemy) -> bool:
    kind, _, _, _ = pick_enemy_target(game, enemy)
    return kind == "base"


def _enemy_attacking_base(game: "GameSession", enemy: Enemy) -> bool:
    """敌人已进入对基地的攻击站位（含远程停火距离）。"""
    if not enemy.alive or not _enemy_targets_base(game, enemy):
        return False
    _, tx, ty, _ = pick_enemy_target(game, enemy)
    stop = _stop_distance(enemy, config.BASE_RADIUS)
    return dist(enemy.x, enemy.y, tx, ty) <= stop * 1.08


def _base_under_attack(game: "GameSession") -> bool:
    if getattr(game, "base_alert_timer", 0.0) > 0:
        return True
    return any(_enemy_attacking_base(game, e) for e in game.enemies if e.alive)


def _pick_guard_target(game: "GameSession", guard: Guard) -> Enemy | None:
    if not _any_alive_enemy(game):
        return None
    target = find_target(guard.x, guard.y, game.enemies, guard.seek_range)
    if target or not _base_under_attack(game):
        return target
    extended = guard.seek_range + getattr(config, "GUARD_BASE_ALERT_SEEK_EXTEND", 220)
    return find_target(
        guard.x,
        guard.y,
        game.enemies,
        extended,
        eligible=lambda e: _enemy_targets_base(game, e),
    )


def update_guard_combat(game: "GameSession", guard: Guard, dt: float) -> None:
    if not guard.alive:
        return

    target = _pick_guard_target(game, guard)

    if target:
        stop = guard.attack_range * 0.82 + target.radius
        d = dist(guard.x, guard.y, target.x, target.y)
        if d > stop:
            _move_guard_toward(guard, target.x, target.y, dt)
        guard.attack_cd -= dt
        if (
            guard.attack_cd <= 0
            and dist(guard.x, guard.y, target.x, target.y)
            <= guard.attack_range + target.radius
        ):
            target.take_damage(guard.damage)
            enemy_aggro_guard(game, target, guard)
            guard.attack_cd = 1.0 / max(0.2, guard.attack_rate)
        return

    hx, hy = _guard_home_pos(guard)
    if dist(guard.x, guard.y, hx, hy) > 6.0:
        _move_guard_toward(guard, hx, hy, dt)


def prune_guards(game: "GameSession") -> None:
    for e in game.enemies:
        if not e.alive or e.aggro_guard_uid is None:
            continue
        if _guard_by_uid(game, e.aggro_guard_uid) is None:
            e.aggro_guard_uid = None
    game.guards = [g for g in game.guards if g.alive]
