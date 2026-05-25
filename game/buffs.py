"""本局增益列表（局外 + 强化卡 + 数值汇总）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from game.tower_labels import tower_damage_label

if TYPE_CHECKING:
    from game.session import GameSession


def meta_buff_labels(meta_data: dict, purchased: set[str]) -> list[str]:
    lines: list[str] = []
    for u in meta_data.get("unlocks", []):
        if u["id"] in purchased:
            lines.append(f"{u['name']}：{u['desc']}")
    return lines


def build_buff_lines(game: "GameSession") -> list[str]:
    lines: list[str] = []
    if game.meta_buff_lines:
        lines.append("【局外解锁】")
        lines.extend(game.meta_buff_lines)

    stacks = game.stats.upgrade_stacks
    if stacks:
        lines.append("【本局强化】")
        by_id = {c["id"]: c for c in game.upgrades.pool}
        for uid in sorted(stacks, key=lambda x: by_id.get(x, {}).get("name", x)):
            card = by_id.get(uid)
            n = stacks[uid]
            if card:
                label = f"{card['name']} x{n}" if n > 1 else card["name"]
                lines.append(f"  {label} · {card['desc']}")
            else:
                lines.append(f"  {uid} x{n}")

    summary = _numeric_summary(game)
    if summary:
        lines.append("【当前效果】")
        lines.extend(summary)
    if not lines:
        lines.append("（暂无增益）")
    return lines


def _numeric_summary(game: "GameSession") -> list[str]:
    s = game.stats
    b = game.base
    out: list[str] = []

    if s.base_hp_mult:
        sign = "+" if s.base_hp_mult > 0 else ""
        out.append(f"地基生命 {sign}{int(s.base_hp_mult * 100)}%")
    if s.base_regen > 0:
        out.append(f"地基回复 {s.base_regen:.0f}/秒")
    if s.base_thorns > 0:
        out.append(f"反伤 {s.base_thorns}/次")
    if b.pulse_enabled or s.base_pulse:
        from game.base_pulse import pulse_params

        params = pulse_params(s)
        if params:
            dmg, radius, pulse_cd = params
            out.append(f"脉冲环：每{pulse_cd:.1f}秒 · 半径{radius:.0f} · 伤害{dmg:.0f}")
    if s.base_aura_slow > 0:
        import config

        out.append(
            f"基地寒场：半径{config.BASE_AURA_RADIUS:.0f} "
            f"减速 {int(s.base_aura_slow * 100)}%"
        )
    if s.base_shield > 0 or b.shield > 0:
        sh = f"护盾 {int(b.shield)}"
        if s.base_shield > 0:
            sh += f"/{int(s.base_shield)}"
        if s.base_shield_regen > 0:
            sh += f" · {s.base_shield_regen:.0f}/秒回盾"
        out.append(sh)
    if s.kill_heal > 0:
        out.append(f"击杀回复 {s.kill_heal}/只")
    if s.tower_damage_mult:
        out.append(f"全塔伤害 +{int(s.tower_damage_mult * 100)}%")
    if s.tower_fire_rate_mult:
        out.append(f"全塔攻速 +{int(s.tower_fire_rate_mult * 100)}%")
    if s.tower_range_mult:
        out.append(f"全塔射程 +{int(s.tower_range_mult * 100)}%")
    for tid, v in s.type_damage.items():
        if v:
            out.append(f"{tower_damage_label(tid, game.tower_defs)} +{int(v * 100)}%")
    if s.slow_mult:
        out.append(f"寒塔减速 +{int(s.slow_mult * 100)}%")
    if s.splash_mult:
        out.append(f"重炮爆炸范围 +{int(s.splash_mult * 100)}%")
    if s.double_shot_chance:
        out.append(f"箭塔双发 {int(min(100, s.double_shot_chance * 100))}%")
    if s.laser_ramp_mult:
        out.append(f"激光蓄能 +{int(s.laser_ramp_mult * 100)}%")
    if s.laser_cap_mult:
        out.append(f"激光上限 +{int(s.laser_cap_mult * 100)}%")
    if s.laser_range_mult:
        out.append(f"激光射程 +{int(s.laser_range_mult * 100)}%")
    if s.laser_sweep_unlock:
        out.append("激光广域扫射")
    if s.wind_fan_mult:
        out.append(f"风塔扇形 +{int(s.wind_fan_mult * 100)}%")
    if s.wind_knockback_mult:
        out.append(f"风塔击退 +{int(s.wind_knockback_mult * 100)}%")
    if s.wind_rate_mult:
        out.append(f"风塔攻速 +{int(s.wind_rate_mult * 100)}%")
    if s.wind_range_mult:
        out.append(f"风塔射程 +{int(s.wind_range_mult * 100)}%")
    if s.barracks_spawn_rate_mult:
        out.append(f"兵营生成加速 +{int(s.barracks_spawn_rate_mult * 100)}%")
    if s.barracks_guard_hp_mult:
        out.append(f"护卫生命 +{int(s.barracks_guard_hp_mult * 100)}%")
    if s.barracks_guard_damage_mult:
        out.append(f"护卫伤害 +{int(s.barracks_guard_damage_mult * 100)}%")
    if s.barracks_guard_rate_mult:
        out.append(f"护卫攻速 +{int(s.barracks_guard_rate_mult * 100)}%")
    if s.barracks_max_guards_bonus:
        out.append(f"护卫总上限 +{s.barracks_max_guards_bonus}")
    if s.barracks_spawn_count_bonus:
        out.append(f"每次多召 +{s.barracks_spawn_count_bonus} 护卫")
    if s.mint_yield_mult:
        out.append(f"钱塔产金 +{int(s.mint_yield_mult * 100)}%")
    if s.mint_rate_mult:
        out.append(f"钱塔结算加速 +{int(s.mint_rate_mult * 100)}%")
    if s.mint_range_mult:
        out.append(f"钱塔射程 +{int(s.mint_range_mult * 100)}%")
    if s.mint_cap_mult:
        out.append(f"钱塔单次上限 +{int(s.mint_cap_mult * 100)}%")
    if s.exp_mult:
        out.append(f"经验 +{int(s.exp_mult * 100)}%")
    if s.gold_mult:
        out.append(f"金币 +{int(s.gold_mult * 100)}%")
    if s.build_cost_mult:
        out.append(f"建塔费用 {int(s.build_cost_mult * 100)}%")
    if s.xp_need_mult:
        out.append(f"升级经验需求 {int(s.xp_need_mult * 100)}%")
    if s.enemy_hp_mult:
        out.append(f"敌人生命 {int(s.enemy_hp_mult * 100)}%")
    if s.max_layers_bonus:
        out.append(f"塔层上限 +{s.max_layers_bonus}")
    return out
