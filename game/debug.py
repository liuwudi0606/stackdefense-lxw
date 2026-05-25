"""调试菜单指令。"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

import config
from game.iso import spawn_at_edge

if TYPE_CHECKING:
    from game.session import GameSession


def debug_add_gold(game: "GameSession", amount: int) -> None:
    game.gold += amount


def debug_clear_enemies(game: "GameSession") -> None:
    game.enemies.clear()
    game.bullets.clear()
    if (
        game.endless_mode
        and game.waves.endless
        and game.waves.all_scheduled_spawned
    ):
        game.waves._endless_cd = min(
            game.waves._endless_cd, config.ENDLESS_INITIAL_COOLDOWN
        )


def debug_heal_base(game: "GameSession") -> None:
    game.base.hp = game.base.max_hp
    game.base.shield = max(game.base.shield, 50)


def debug_add_level(game: "GameSession") -> None:
    game.level += 1
    game.pending_level_ups += 1
    game._try_open_upgrade_pick()


def debug_add_exp(game: "GameSession") -> None:
    game.add_exp(game.xp_to_next())


def debug_spawn_pack(game: "GameSession", count: int = 8) -> None:
    types = list(game.enemy_defs.keys())
    for _ in range(count):
        tid = random.choice(types)
        x, y = spawn_at_edge()
        game.spawn_enemy(tid, x, y)


def debug_grant_upgrade(game: "GameSession", card_id: str) -> bool:
    card = game.base_upgrades.find(card_id)
    if card:
        if game.base_upgrades.is_maxed(game.stats, card):
            return False
        from game.upgrades import apply_upgrade_card

        old_hp_stat = game.stats.enemy_hp_mult
        apply_upgrade_card(card, game.stats, game)
        if "enemy_hp_mult" in (card.get("effect") or {}):
            game.rescale_living_enemies_hp_buff(old_hp_stat)
        game.picked_upgrades.append(card["name"])
        return True
    card = next((c for c in game.upgrades.pool if c["id"] == card_id), None)
    if not card:
        return False
    uid = card["id"]
    max_s = card.get("max_stacks", 99)
    if game.stats.upgrade_stacks.get(uid, 0) >= max_s:
        return False
    old_hp_stat = game.stats.enemy_hp_mult
    game.upgrades.apply_choice(card, game.stats, game)
    if "enemy_hp_mult" in (card.get("effect") or {}):
        game.rescale_living_enemies_hp_buff(old_hp_stat)
    game.picked_upgrades.append(card["name"])
    return True


def debug_toggle_god(game: "GameSession") -> bool:
    game.debug_god_mode = not game.debug_god_mode
    return game.debug_god_mode


def debug_toggle_endless(game: "GameSession") -> bool:
    """开：跳过预定波次并进入无尽刷怪；关：关闭无尽模式。"""
    if game.endless_mode:
        game.set_endless_mode(False)
        return False
    debug_skip_to_endless(game)
    return True


def debug_skip_to_endless(game: "GameSession") -> None:
    """调试：跳过剩余预定波次，立即进入无尽刷怪阶段。"""
    game.waves.wave_index = len(game.waves.waves)
    game.waves.spawn_queue.clear()
    game.waves.all_scheduled_spawned = True
    game.set_endless_mode(True)
