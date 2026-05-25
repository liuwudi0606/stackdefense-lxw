"""塔详情数值（含局内 buff 与等级）。"""



from __future__ import annotations

import math

import config
from typing import TYPE_CHECKING



from game.laser_combat import (
    laser_dps,
    laser_fire_rate_factor,
    laser_mode_label,
    laser_phase,
    laser_ramp_mult,
    laser_range,
    laser_sweep_dps,
)
from game.barracks_combat import (
    barracks_max_guards,
    barracks_spawn_count,
    barracks_spawn_interval,
    guard_stats_from_tower,
)
from game.wind_combat import (
    wind_fan_half_angle_rad,
    wind_fire_rate,
    wind_knockback,
    wind_range,
)
from game.mint_combat import (
    MINT_HOARD_MIN_ENEMIES,
    calc_mint_gold,
    count_enemies_in_mint_range,
    mint_interval,
    mint_range,
    mint_range_breakdown,
)
from game.tower_range_bands import fixed_inner_radius, fixed_outer_radius



if TYPE_CHECKING:

    from game.entities import TowerFloor

    from game.session import GameSession





def _laser_stat_lines(game: "GameSession", tdef: dict, tower: "TowerFloor | None" = None) -> list[str]:

    charge = tower.laser_charge if tower else 0.0

    fr = laser_fire_rate_factor(game, tower)
    ramp = laser_ramp_mult(
        tdef,
        charge,
        game.stats.laser_ramp_mult,
        game.stats.laser_cap_mult,
        fire_rate_factor=fr,
    )

    base = tdef["base_dps"] * game.stats.tower_damage_factor("laser")

    if tower:

        base *= game.tower_damage_mult(tower)

    max_ramp = tdef.get("max_ramp_mult", 12) * (1.0 + game.stats.laser_cap_mult)

    max_dps = tdef["base_dps"] * max_ramp * game.stats.tower_damage_factor("laser")

    if tower:

        max_dps *= game.tower_damage_mult(tower)

    cur_dps = base * ramp if tower else base

    phase = laser_phase(tdef, charge)

    sweep_dps = laser_sweep_dps(game, tower, tdef) if tower else base
    mode = laser_mode_label(game, tower, tdef) if tower else "单体蓄能"
    lines = [
        f"攻击模式 {mode}",
        f"秒伤 {cur_dps:.1f}（当前）· 上限 {max_dps:.1f}",
        f"扫射 {sweep_dps:.1f}/秒" if game.stats.laser_sweep_unlock else "",
        f"蓄能 +{tdef.get('ramp_per_sec', 0.35) * (1 + game.stats.laser_ramp_mult) * fr:.2f}/秒",
        f"光柱阶段 {phase}/3",
        "单体优先高血量",
    ]
    lines = [ln for ln in lines if ln]

    if tower and game.stats.laser_sweep_unlock:
        smart = "开" if tower.laser_auto else "关"
        manual = "扫射" if tower.laser_mode == "sweep" else "单体"
        lines.append(f"智能 {smart} · 手动 {manual}")
        if tower.laser_auto:
            from game.laser_combat import (
                enemies_in_laser_range,
                laser_range,
                laser_single_peak_dps,
                laser_sweep_total_dps,
            )

            rng = laser_range(tdef, game.stats)
            in_range = enemies_in_laser_range(game.enemies, rng)
            if in_range:
                sweep_sum = laser_sweep_total_dps(game, tower, tdef, rng, in_range)
                single_peak = laser_single_peak_dps(
                    game, tower, tdef, rng, in_range
                )
                pick = "扫射" if sweep_sum > single_peak else "单体"
                lines.append(
                    f"智能判定 {pick}（合计{sweep_sum:.0f} vs 峰值{single_peak:.0f}）"
                )

    if tower and tower.laser_sweeping:
        lines.append("扫射范围内全部敌人")
    elif tower and tower.laser_target and tower.laser_target.alive:
        lines.append(f"锁定中：{game.enemy_defs.get(tower.laser_target.type_id, {}).get('name', '?')}")

    return lines


def _barracks_stat_lines(game: "GameSession", tdef: dict, tower: "TowerFloor | None" = None) -> list[str]:
    class _Lvl:
        level = 1

    tw = tower if tower else _Lvl()
    interval = barracks_spawn_interval(tdef, tw, game.stats)
    count = barracks_spawn_count(tdef, tw, game.stats)
    cap = barracks_max_guards(tdef, game.stats, game)
    per = tdef.get("max_guards", 7)
    n_bar = sum(1 for t in game.towers if t.type_id == "barracks") or 1
    g = guard_stats_from_tower(game, tdef, tw) if tower else guard_stats_from_tower(
        game, tdef, _Lvl()
    )
    alive = sum(1 for x in game.guards if x.alive) if tower else 0
    lines = [
        f"生成 {count} 人 / {interval:.1f}秒（基地外环·朝最近敌人）",
        f"场上上限 {cap}（{n_bar}座×{per}人/座，当前 {alive}）",
        f"护卫生命 {g['max_hp']:.0f}",
        f"护卫伤害 {g['damage']:.1f}/击 · {g['attack_rate']:.2f}/秒",
        f"护卫近战射程 {int(g['attack_range'])}",
        f"寻敌范围 {int(g['seek_range'])} · 移速 {int(g['move_speed'])}",
    ]
    return lines


def _mint_stat_lines(game: "GameSession", tdef: dict, tower: "TowerFloor | None" = None) -> list[str]:
    class _Lvl:
        level = 1

    tw = tower if tower else _Lvl()
    rng = mint_range(tdef, game.stats)
    interval = mint_interval(tdef, tw, game.stats)
    cap = float(tdef.get("mint_cap", 48)) * (1.0 + game.stats.mint_cap_mult)
    per = float(tdef.get("mint_per_enemy", 4)) * (1.0 + game.stats.mint_yield_mult)
    base = float(tdef.get("mint_base", 1))
    ring_in = int(fixed_inner_radius())
    ring_out = int(fixed_outer_radius())
    if tower:
        inner_n, far_n, beyond_n, n = mint_range_breakdown(game, rng)
        est = calc_mint_gold(game, tdef, tower, n)
        total = int(getattr(tower, "mint_total_gold", 0))
        lines = [
            "伤害 无（产金）",
            f"累计获得 {total} 金",
            f"结算间隔 {interval:.1f}秒",
            f"塔射程 {int(rng)} · 固定内/外圈 {ring_in}/{ring_out}",
            f"内 {inner_n} · 中外环 {far_n}×50% · 超远 {beyond_n}（计 {n:.1f}）· 约 +{est} 金",
            f"每名 +{per:.1f} 金 · 射程>{ring_out} 后超远圈全额 · 上限 {cap:.0f}",
        ]
        if game.stats.mint_hoard_mult > 0:
            lines.append(
                f"囤积红利：>{MINT_HOARD_MIN_ENEMIES}敌后每多1名 +"
                f"{per * game.stats.mint_hoard_mult:.1f} 金"
            )
    else:
        lines = [
            "伤害 无（产金）",
            f"结算间隔 {interval:.1f}秒",
            f"塔射程 {int(rng)} · 固定圈 {ring_in}/{ring_out}（中外环 50% 计敌）",
            f"基础 {base:.0f} + 每名 {per:.1f} 金 · 超远圈需射程>{ring_out}",
            f"单次上限 {cap:.0f}（无敌人时收益很低）",
        ]
        if game.stats.mint_hoard_mult > 0:
            lines.append(
                f"囤积：超过{MINT_HOARD_MIN_ENEMIES}名敌人后，每多1名额外产金"
            )
    return lines


def _wind_stat_lines(game: "GameSession", tdef: dict, tower: "TowerFloor | None" = None) -> list[str]:
    class _Lvl:
        level = 1

    tw = tower if tower else _Lvl()
    half_deg = math.degrees(wind_fan_half_angle_rad(tdef, tw, game.stats.wind_fan_mult)) * 2
    kb = wind_knockback(tdef, tw, game.stats.wind_knockback_mult)
    rate = (
        wind_fire_rate(tdef, tower, game.stats)
        if tower
        else tdef["fire_rate"] * (1.0 + game.stats.tower_fire_rate_mult + game.stats.wind_rate_mult)
    )
    rng = int(wind_range(tdef, game.stats))
    ring_out = int(fixed_outer_radius())
    return [
        "伤害 无（仅击退）",
        f"攻速 {rate:.2f}/秒",
        f"塔射程 {rng} · 固定圈 {int(fixed_inner_radius())}/{ring_out}（中外环 50% 击退）",
        f"扇形宽度 {half_deg:.0f}°",
        f"击退力度 {kb:.0f}",
    ]


def tower_stat_lines(game: "GameSession", tower: "TowerFloor", tower_index: int | None = None) -> list[str]:

    tdef = game.tower_defs[tower.type_id]

    idx = tower_index if tower_index is not None else game.towers.index(tower)

    if tower.type_id == "laser":

        lines = _laser_stat_lines(game, tdef, tower)

        rng = int(laser_range(tdef, game.stats))
        ring_out = int(fixed_outer_radius())

        lines.insert(
            2,
            f"塔射程 {rng} · 固定圈 {int(fixed_inner_radius())}/{ring_out}"
            + (f" · 超远+{rng - ring_out}" if rng > ring_out else "（满额需>{ring_out}）"),
        )

    elif tower.type_id == "wind":

        lines = _wind_stat_lines(game, tdef, tower)

    elif tower.type_id == "barracks":

        lines = _barracks_stat_lines(game, tdef, tower)

    elif tower.type_id == "mint":

        lines = _mint_stat_lines(game, tdef, tower)

    else:

        dmg = (

            tdef["damage"]

            * game.stats.tower_damage_factor(tower.type_id)

            * game.tower_damage_mult(tower)

        )

        rate = tdef["fire_rate"] * (1.0 + game.stats.tower_fire_rate_mult) * game.tower_fire_rate_mult(

            tower

        )

        rng = int(tdef["range"] * (1.0 + game.stats.tower_range_mult))
        ring_out = int(fixed_outer_radius())

        lines = [

            f"伤害 {dmg:.1f}/发",

            f"攻速 {rate:.2f}/秒",

            f"塔射程 {rng} · 固定圈 {int(fixed_inner_radius())}/{ring_out}"
            + (f" · 超远全额" if rng > ring_out else "（中外环 50%）"),

        ]

    lines.extend(

        [

            f"建造 {game.build_cost(tower.type_id)} 金",

            f"升级 {game.upgrade_tower_cost(idx)} 金",

        ]

    )

    if tower.type_id == "slow":

        slow_base = tdef.get("slow_factor", 0.5)

        slow_f = slow_base * max(0.2, 1.0 - game.stats.slow_mult)

        lines.append(f"减速至 {slow_f:.0%} 移速 · {tdef.get('slow_duration', 2)}秒")

    if tower.type_id == "cannon":

        splash = tdef.get("splash_radius", 40) * (1.0 + game.stats.splash_mult)

        sec = int(config.CANNON_SPLASH_SECONDARY_MULT * 100)
        lines.append(f"爆炸半径 {splash:.0f}（溅射目标 {sec}% 伤害）")

    if tower.type_id == "arrow" and game.stats.double_shot_chance > 0:

        pct = int(min(100, game.stats.double_shot_chance * 100))

        lines.append(f"双发概率 {pct}%")

    desc = tdef.get("desc", "")

    if desc:

        lines.append(f"说明：{desc}")

    return lines





def tower_preview_lines(game: "GameSession", type_id: str) -> list[str]:

    """建造栏详情：未放置塔的数值预览。"""

    tdef = game.tower_defs[type_id]

    if type_id == "laser":

        lines = _laser_stat_lines(game, tdef, None)

        rng = int(laser_range(tdef, game.stats))
        ring_out = int(fixed_outer_radius())

        lines.insert(
            2,
            f"塔射程 {rng} · 固定圈 {int(fixed_inner_radius())}/{ring_out}"
            + (f" · 超远+{rng - ring_out}" if rng > ring_out else "（满额需>{ring_out}）"),
        )

        lines.append(f"建造 {game.build_cost(type_id)} 金")

    elif type_id == "wind":

        lines = _wind_stat_lines(game, tdef, None)

        lines.append(f"建造 {game.build_cost(type_id)} 金")

    elif type_id == "barracks":

        lines = _barracks_stat_lines(game, tdef, None)

        lines.append(f"建造 {game.build_cost(type_id)} 金")

    elif type_id == "mint":

        lines = _mint_stat_lines(game, tdef, None)

        lines.append(f"建造 {game.build_cost(type_id)} 金")

    else:

        dmg = tdef["damage"] * game.stats.tower_damage_factor(type_id)

        rate = tdef["fire_rate"] * (1.0 + game.stats.tower_fire_rate_mult)

        rng = int(tdef["range"] * (1.0 + game.stats.tower_range_mult))
        ring_out = int(fixed_outer_radius())

        lines = [

            f"伤害 {dmg:.1f}/发",

            f"攻速 {rate:.2f}/秒",

            f"塔射程 {rng} · 固定圈 {int(fixed_inner_radius())}/{ring_out}"
            + (f" · 超远全额" if rng > ring_out else "（中外环 50%）"),

            f"建造 {game.build_cost(type_id)} 金",

        ]

    if type_id == "slow":

        slow_base = tdef.get("slow_factor", 0.5)

        slow_f = slow_base * max(0.2, 1.0 - game.stats.slow_mult)

        lines.append(f"减速至 {slow_f:.0%} 移速 · {tdef.get('slow_duration', 2)}秒")

    if type_id == "cannon":

        splash = tdef.get("splash_radius", 40) * (1.0 + game.stats.splash_mult)

        sec = int(config.CANNON_SPLASH_SECONDARY_MULT * 100)
        lines.append(f"爆炸半径 {splash:.0f}（溅射目标 {sec}% 伤害）")

    if type_id == "arrow" and game.stats.double_shot_chance > 0:

        pct = int(min(100, game.stats.double_shot_chance * 100))

        lines.append(f"双发概率 {pct}%")

    desc = tdef.get("desc", "")

    if desc:

        lines.append(f"说明：{desc}")

    return lines


