"""局内存档（自动保存 / 继续游戏）。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import config
from game.storage import RUN_STORAGE_KEY, delete_stored, has_stored, read_json, write_json

if TYPE_CHECKING:
    from game.session import GameSession

RUN_SAVE_PATH = config.ROOT / "run_save.json"


def has_run_save() -> bool:
    return has_stored(RUN_SAVE_PATH, web_key=RUN_STORAGE_KEY)


def delete_run_save() -> None:
    delete_stored(RUN_SAVE_PATH, web_key=RUN_STORAGE_KEY)


def _spawn_queue_to_json(queue: list) -> list:
    out = []
    for item in queue:
        if len(item) >= 3:
            t, etype, opts = item[0], item[1], item[2]
            row: list = [float(t), str(etype)]
            if opts:
                row.append(opts)
            out.append(row)
        else:
            out.append([float(item[0]), str(item[1])])
    return out


def _spawn_queue_from_json(raw: list) -> list[tuple[float, str, dict]]:
    q: list[tuple[float, str, dict]] = []
    for item in raw:
        if len(item) >= 3:
            opts = item[2] if isinstance(item[2], dict) else {}
            q.append((float(item[0]), str(item[1]), opts))
        else:
            q.append((float(item[0]), str(item[1]), {}))
    return q


def _stats_to_dict(stats) -> dict:
    return {
        "base_hp_mult": stats.base_hp_mult,
        "base_regen": stats.base_regen,
        "base_thorns": stats.base_thorns,
        "base_pulse": stats.base_pulse,
        "base_aura_slow": stats.base_aura_slow,
        "base_shield": stats.base_shield,
        "base_shield_regen": stats.base_shield_regen,
        "kill_heal": stats.kill_heal,
        "tower_damage_mult": stats.tower_damage_mult,
        "tower_fire_rate_mult": stats.tower_fire_rate_mult,
        "tower_range_mult": stats.tower_range_mult,
        "type_damage": dict(stats.type_damage),
        "slow_mult": stats.slow_mult,
        "splash_mult": stats.splash_mult,
        "double_shot_chance": stats.double_shot_chance,
        "laser_ramp_mult": stats.laser_ramp_mult,
        "laser_cap_mult": stats.laser_cap_mult,
        "laser_range_mult": stats.laser_range_mult,
        "laser_sweep_unlock": stats.laser_sweep_unlock,
        "wind_fan_mult": stats.wind_fan_mult,
        "wind_knockback_mult": stats.wind_knockback_mult,
        "wind_rate_mult": stats.wind_rate_mult,
        "wind_range_mult": stats.wind_range_mult,
        "barracks_spawn_rate_mult": stats.barracks_spawn_rate_mult,
        "barracks_guard_hp_mult": stats.barracks_guard_hp_mult,
        "barracks_guard_damage_mult": stats.barracks_guard_damage_mult,
        "barracks_guard_rate_mult": stats.barracks_guard_rate_mult,
        "barracks_max_guards_bonus": stats.barracks_max_guards_bonus,
        "barracks_spawn_count_bonus": stats.barracks_spawn_count_bonus,
        "exp_mult": stats.exp_mult,
        "gold_mult": stats.gold_mult,
        "build_cost_mult": stats.build_cost_mult,
        "xp_need_mult": stats.xp_need_mult,
        "enemy_hp_mult": stats.enemy_hp_mult,
        "max_layers_bonus": stats.max_layers_bonus,
        "unlocked_towers": sorted(stats.unlocked_towers),
        "upgrade_stacks": dict(stats.upgrade_stacks),
    }


def _stats_from_dict(stats, d: dict) -> None:
    for k, v in d.items():
        if k == "unlocked_towers":
            stats.unlocked_towers = set(v)
        elif k == "type_damage":
            stats.type_damage = dict(v)
        elif k == "upgrade_stacks":
            stats.upgrade_stacks = dict(v)
        elif hasattr(stats, k):
            setattr(stats, k, v)


def _state_for_save(game: "GameSession") -> str:
    """单位菜单状态不写入存档，避免恢复后战斗暂停且菜单不显示。"""
    from game.session import GameState

    if game.state in (
        GameState.TOWER_MENU,
        GameState.TOWER_SWAP,
        GameState.ENEMY_MENU,
    ):
        return GameState.PLAYING.name
    return game.state.name


def _normalize_loaded_ui(game: "GameSession") -> None:
    from game.session import GameState

    if game.state == GameState.TOWER_MENU:
        idx = game.selected_tower_index
        if idx is None or idx < 0 or idx >= len(game.towers):
            game.close_tower_ui()
    elif game.state == GameState.TOWER_SWAP:
        idx = game.selected_tower_index
        if idx is None or idx < 0 or idx >= len(game.towers):
            game.close_tower_ui()
    elif game.state == GameState.ENEMY_MENU:
        idx = game.selected_enemy_index
        if idx is None or idx < 0 or idx >= len(game.enemies):
            game.close_enemy_ui()
        elif not game.enemies[idx].alive:
            game.close_enemy_ui()

    game.scroll_drag = None
    game.ui_scroll_y = 0
    game.buff_panel_open = False
    game.debug_menu_open = False
    game.debug_buff_info = None
    game.build_info_tower = None
    game.build_drag = None


def _enemy_index_for_save(game: "GameSession"):
    from game.session import GameState

    if game.state == GameState.ENEMY_MENU:
        return game.selected_enemy_index
    return None


def serialize_run(game: "GameSession") -> dict:
    from game.camera import view_state_dict

    b = game.base
    return {
        "version": 1,
        "view": view_state_dict(),
        "endless_mode": game.endless_mode,
        "clear_reward_applied": game.clear_reward_applied,
        "win_token_gain": game.win_token_gain,
        "state": _state_for_save(game),
        "gold": game.gold,
        "exp": game.exp,
        "level": game.level,
        "pending_level_ups": game.pending_level_ups,
        "build_types": list(game.build_types),
        "build_info_tower": game.build_info_tower,
        "ui_scroll_y": game.ui_scroll_y,
        "selected_build": game.selected_build,
        "selected_enemy_index": _enemy_index_for_save(game),
        "picked_upgrades": list(game.picked_upgrades),
        "max_tower_floors": game.max_tower_floors,
        "meta_hp_mult": game.meta_hp_mult,
        "meta_buff_lines": list(game.meta_buff_lines),
        "stats": _stats_to_dict(game.stats),
        "base": {
            "hp": b.hp,
            "max_hp": b.max_hp,
            "shield": b.shield,
            "pulse_timer": b.pulse_timer,
            "pulse_enabled": b.pulse_enabled,
        },
        "towers": [
            {
                "type_id": t.type_id,
                "floor": t.floor,
                "level": t.level,
                "cooldown": t.cooldown,
                "laser_charge": t.laser_charge,
                "laser_break_timer": t.laser_break_timer,
                "laser_mode": t.laser_mode,
                "laser_auto": t.laser_auto,
                "laser_target_index": (
                    game.enemies.index(t.laser_target)
                    if t.laser_target and t.laser_target in game.enemies
                    else None
                ),
            }
            for t in game.towers
        ],
        "enemies": [
            {
                "type_id": e.type_id,
                "x": e.x,
                "y": e.y,
                "hp": e.hp,
                "max_hp": e.max_hp,
                "speed": e.speed,
                "exp": e.exp,
                "gold": e.gold,
                "radius": e.radius,
                "color": list(e.color),
                "slow_timer": e.slow_timer,
                "slow_factor": e.slow_factor,
                "weakened": e.weakened,
                "buffed": e.buffed,
                "attack_mode": e.attack_mode,
                "damage": e.damage,
                "attack_range": e.attack_range,
                "attack_rate": e.attack_rate,
                "attack_cd": e.attack_cd,
                "aggro_guard_uid": e.aggro_guard_uid,
                "laser_resist": e.laser_resist,
                "laser_vuln": e.laser_vuln,
                "wind_resist": e.wind_resist,
                "skill_cds": dict(e.skill_cds),
                "skill_flags": dict(e.skill_flags),
            }
            for e in game.enemies
            if e.alive
        ],
        "guards": [
            {
                "uid": g.uid,
                "x": g.x,
                "y": g.y,
                "hp": g.hp,
                "max_hp": g.max_hp,
                "damage": g.damage,
                "attack_range": g.attack_range,
                "attack_rate": g.attack_rate,
                "radius": g.radius,
                "move_speed": g.move_speed,
                "seek_range": g.seek_range,
                "spawn_x": g.spawn_x,
                "spawn_y": g.spawn_y,
                "attack_cd": g.attack_cd,
                "source_floor": g.source_floor,
            }
            for g in game.guards
            if g.alive
        ],
        "guard_uid": game._guard_uid,
        "waves": {
            "elapsed": game.waves.elapsed,
            "wave_index": game.waves.wave_index,
            "spawn_queue": _spawn_queue_to_json(game.waves.spawn_queue),
            "all_scheduled_spawned": game.waves.all_scheduled_spawned,
            "endless_cycle": game.waves.endless_cycle,
            "_endless_cd": game.waves._endless_cd,
        },
        "upgrade_choices": [
            {"id": c["id"], "name": c["name"]} for c in game.upgrade_choices
        ],
    }


def save_run(game: "GameSession") -> None:
    from game.session import GameState

    if game.state in (GameState.WON, GameState.LOST):
        return
    # 通关询问界面可存档，避免误退后丢失进度
    write_json(RUN_SAVE_PATH, serialize_run(game), web_key=RUN_STORAGE_KEY)


def load_run_into(game: "GameSession", data: dict) -> None:
    from copy import deepcopy

    from game.camera import load_view_state
    from game.entities import Base, Enemy, Guard, TowerFloor
    from game.session import GameState
    from game.upgrades import find_upgrade

    load_view_state(data.get("view"))

    game.endless_mode = data.get("endless_mode", config.ENDLESS_MODE)
    game.clear_reward_applied = bool(data.get("clear_reward_applied", False))
    game.win_token_gain = int(data.get("win_token_gain", 0))
    game.gold = data["gold"]
    game.exp = data["exp"]
    game.level = data["level"]
    game.pending_level_ups = data.get("pending_level_ups", 0)
    game.build_types = list(data["build_types"])
    raw_sel = data.get("selected_build")
    game.selected_build = raw_sel if raw_sel in game.build_types else None
    game.build_info_tower = data.get("build_info_tower")
    game.ui_scroll_y = data.get("ui_scroll_y", 0)
    game.picked_upgrades = list(data.get("picked_upgrades", []))
    game.max_tower_floors = data.get("max_tower_floors", config.MAX_TOWER_FLOORS_DEFAULT)
    game.meta_hp_mult = data.get("meta_hp_mult", 0.0)
    game.meta_buff_lines = list(data.get("meta_buff_lines", []))

    _stats_from_dict(game.stats, data["stats"])

    bd = data["base"]
    game.base = Base(
        hp=bd["hp"],
        max_hp=bd["max_hp"],
        shield=bd.get("shield", 0),
        pulse_timer=bd.get("pulse_timer", 0),
        pulse_enabled=bd.get("pulse_enabled", False),
    )
    if game.stats.base_pulse:
        game.base.pulse_enabled = True

    game.enemies = []
    for ed in data.get("enemies", []):
        d = game.enemy_defs.get(ed["type_id"], {})
        atk = ed.get("attack_mode", d.get("attack", "melee"))
        game.enemies.append(
            Enemy(
                type_id=ed["type_id"],
                x=ed["x"],
                y=ed["y"],
                hp=ed["hp"],
                max_hp=ed["max_hp"],
                speed=ed["speed"],
                exp=ed["exp"],
                gold=ed["gold"],
                radius=ed["radius"],
                color=tuple(ed["color"]),
                slow_timer=ed.get("slow_timer", 0),
                slow_factor=ed.get("slow_factor", 1.0),
                weakened=ed.get("weakened", False),
                buffed=ed.get("buffed", False),
                attack_mode=atk,
                damage=float(ed.get("damage", d.get("damage", 6))),
                attack_range=float(
                    ed.get(
                        "attack_range",
                        d.get(
                            "attack_range",
                            165 if atk == "ranged" else config.BASE_RADIUS + 8,
                        ),
                    )
                ),
                attack_rate=float(ed.get("attack_rate", d.get("attack_rate", 1.0))),
                attack_cd=float(ed.get("attack_cd", 0)),
                aggro_guard_uid=ed.get("aggro_guard_uid"),
                laser_resist=float(ed.get("laser_resist", d.get("laser_resist", 1.0))),
                laser_vuln=float(ed.get("laser_vuln", d.get("laser_vuln", 1.0))),
                wind_resist=float(ed.get("wind_resist", d.get("wind_resist", 1.0))),
                skill_cds={str(k): float(v) for k, v in ed.get("skill_cds", {}).items()},
                skill_flags={str(k): bool(v) for k, v in ed.get("skill_flags", {}).items()},
            )
        )

    game.towers = []
    for t in data.get("towers", []):
        laser_target = None
        idx = t.get("laser_target_index")
        if idx is not None and 0 <= idx < len(game.enemies):
            laser_target = game.enemies[idx]
        game.towers.append(
            TowerFloor(
                type_id=t["type_id"],
                floor=t["floor"],
                level=t.get("level", 1),
                cooldown=t.get("cooldown", 0),
                laser_target=laser_target,
                laser_charge=float(t.get("laser_charge", 0.0)),
                laser_break_timer=float(t.get("laser_break_timer", 0.0)),
                laser_mode=t.get("laser_mode", "single"),
                laser_auto=bool(t.get("laser_auto", True)),
            )
        )

    game.guards = []
    game._guard_uid = int(data.get("guard_uid", 0))
    for gd in data.get("guards", []):
        game.guards.append(
            Guard(
                uid=int(gd["uid"]),
                x=gd["x"],
                y=gd["y"],
                hp=gd["hp"],
                max_hp=gd["max_hp"],
                damage=gd["damage"],
                attack_range=gd["attack_range"],
                attack_rate=gd["attack_rate"],
                radius=gd.get("radius", 11),
                move_speed=gd.get("move_speed", config.GUARD_MOVE_SPEED_DEFAULT),
                seek_range=gd.get("seek_range", config.GUARD_SEEK_RANGE_DEFAULT),
                spawn_x=gd.get("spawn_x", gd["x"]),
                spawn_y=gd.get("spawn_y", gd["y"]),
                attack_cd=gd.get("attack_cd", 0),
                source_floor=gd.get("source_floor", 0),
            )
        )
    if game.guards:
        game._guard_uid = max(game._guard_uid, max(g.uid for g in game.guards))

    w = data.get("waves", {})
    game.waves.elapsed = w.get("elapsed", 0)
    game.waves.wave_index = w.get("wave_index", 0)
    game.waves.spawn_queue = _spawn_queue_from_json(w.get("spawn_queue", []))
    game.waves.all_scheduled_spawned = w.get("all_scheduled_spawned", False)
    game.waves.endless_cycle = w.get("endless_cycle", 0)
    game.waves.endless = game.endless_mode
    if game.endless_mode and game.waves.all_scheduled_spawned:
        game.waves._endless_cd = float(
            w.get("_endless_cd", config.ENDLESS_INITIAL_COOLDOWN)
        )
    elif not game.endless_mode:
        game.waves._endless_cd = 999999.0

    try:
        game.state = GameState[data["state"]]
    except KeyError:
        game.state = GameState.PLAYING

    game.bullets = []
    game.explosions = []
    game.world_fx = []
    game.upgrade_choices = []
    if game.state == GameState.UPGRADE_PICK:
        restored: list[dict] = []
        for item in data.get("upgrade_choices", []):
            card = find_upgrade(game.upgrades.pool, item.get("id", ""))
            if card:
                restored.append(deepcopy(card))
        if restored:
            game.upgrade_choices = restored[:4]
        else:
            game.upgrade_choices = game.upgrades.roll_four(
                game.stats, {t.type_id for t in game.towers}, game
            )

    game.selected_tower_index = None
    game.selected_enemy_index = data.get("selected_enemy_index")
    game.swap_source_index = None
    game.debug_scroll = max(0, int(data.get("debug_scroll", 0)))
    game.scroll_drag = None
    game.buff_panel_open = False
    game.debug_menu_open = False
    game.debug_buff_info = None
    game.build_info_tower = data.get("build_info_tower")
    _normalize_loaded_ui(game)


def load_saved_session(
    tower_defs,
    enemy_defs,
    wave_data,
    upgrade_pool,
    meta_effects=None,
    on_sound=None,
) -> "GameSession | None":
    data = read_json(RUN_SAVE_PATH, web_key=RUN_STORAGE_KEY)
    if not data:
        return None
    from game.session import GameSession

    g = GameSession(
        tower_defs,
        enemy_defs,
        wave_data,
        upgrade_pool,
        meta_effects=meta_effects,
        on_sound=on_sound,
    )
    load_run_into(g, data)
    g._stack_focus_floors = len(g.towers)
    return g
