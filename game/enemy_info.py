"""敌人分级与详情文案。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.entities import Enemy
    from game.session import GameSession

TIER_TAGS = {"elite": "精", "boss": "首", "heavy": "甲"}


def enemy_tier(enemy_defs: dict, type_id: str) -> str:
    return enemy_defs.get(type_id, {}).get("tier", "normal")


def enemy_shows_world_hud(enemy_defs: dict, type_id: str) -> bool:
    return enemy_tier(enemy_defs, type_id) != "normal"


def enemy_world_tag(enemy_defs: dict, type_id: str) -> str:
    custom = enemy_defs.get(type_id, {}).get("tag_label")
    if custom:
        return custom
    tier = enemy_tier(enemy_defs, type_id)
    if tier == "boss":
        return "首领"
    if tier == "elite":
        return "精英"
    if tier == "heavy":
        return "重甲"
    return TIER_TAGS.get(tier, "")


def enemy_detail_lines(game: "GameSession", enemy: "Enemy") -> list[str]:
    d = game.enemy_defs[enemy.type_id]
    tier = enemy_tier(game.enemy_defs, enemy.type_id)
    atk_label = "远程" if enemy.attack_mode == "ranged" else "近战"
    lines = [
        f"生命 {int(enemy.hp)} / {int(enemy.max_hp)}",
        f"攻击 {atk_label} · 伤害 {enemy.damage:.0f}/击 · {enemy.attack_rate:.2f}/秒",
        f"移速 {int(enemy.speed)}",
        f"经验 {enemy.exp}  金币 {enemy.gold}",
        f"分级 {tier}",
    ]
    if enemy.attack_mode == "ranged":
        lines.insert(3, f"射程 {int(enemy.attack_range)}")
    if enemy.weakened:
        lines.append("状态：全局虚弱")
    if enemy.buffed:
        lines.append("状态：全局强化")
    if enemy.is_slowed():
        lines.append(f"状态：减速 ({enemy.slow_factor:.0%} 移速)")
    if enemy.in_base_aura:
        lines.append("状态：基地寒场影响中")
    if enemy.laser_resist < 0.99:
        lines.append(f"激光抗性：{int(enemy.laser_resist * 100)}% 伤害")
    if enemy.laser_vuln > 1.01:
        lines.append(f"激光易伤：+{int((enemy.laser_vuln - 1) * 100)}% 伤害")
    if enemy.wind_resist < 0.95:
        lines.append(f"风场抗性：击退效果 {int(enemy.wind_resist * 100)}%")
    if enemy.skill_flags.get("enraged"):
        lines.append("状态：狂暴（攻移速提升）")
    if d.get("attack_cleave"):
        ac = d["attack_cleave"]
        lines.append(
            f"分裂斩：半径{int(ac.get('radius', 70))} "
            f"卫{int(ac.get('guard_damage_mult', 0.6) * 100)}% "
            f"基溅{int(ac.get('base_splash_mult', 0.3) * 100)}%"
        )

    trait = d.get("trait") or d.get("desc")
    if trait:
        lines.append(f"特性：{trait}")

    skill = d.get("skill")
    if skill:
        lines.append(f"技能：{skill}")
    elif d.get("skills"):
        parts = []
        for sk in d["skills"]:
            sid = sk.get("id", "")
            if sid == "enrage":
                parts.append(f"狂暴(<{int(sk.get('hp_below', 0.5)*100)}%血)")
            elif sid == "ground_slam":
                g = int(sk.get("guard_damage", 0))
                parts.append(
                    f"震地{int(sk.get('damage', 0))}伤"
                    + (f"+清卫{g}" if g else "")
                )
            elif sid == "shockwave":
                parts.append(
                    f"冲击波 卫{int(sk.get('guard_damage', 0))}/基{int(sk.get('base_damage', 0))}"
                )
            elif sid == "guard_siege":
                parts.append(
                    f"卫压≥{int(sk.get('min_guards', 5))}卫"
                )
            elif sid == "lightning":
                parts.append(f"雷击{int(sk.get('damage', 0))}伤")
            elif sid == "summon" or sid.startswith("summon_"):
                parts.append(f"召唤{sk.get('spawn', '?')}")
            elif sid == "regen":
                parts.append("再生")
            else:
                parts.append(sid)
        lines.append("技能：" + " · ".join(parts))
    else:
        lines.append("技能：无")

    return lines
