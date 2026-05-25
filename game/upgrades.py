import random
from copy import deepcopy

import config
from game.stats import RunStats
from game.tower_labels import TOWER_TYPE_LABELS, tower_damage_label, tower_label

_BLUEPRINT_TOWERS = frozenset({"cannon", "laser", "wind", "barracks", "mint"})


def required_tower_type(card: dict) -> str | None:
    """该增益生效所需已解锁的塔种；蓝图解锁卡返回 None。"""
    effect = card.get("effect") or {}
    if effect.get("unlock_tower"):
        return None
    td = effect.get("type_damage")
    if isinstance(td, dict) and td:
        return next(iter(td))
    eid = card.get("id", "")
    if eid.startswith("laser_"):
        return "laser"
    if eid.startswith("wind_"):
        return "wind"
    if eid.startswith("barracks_"):
        return "barracks"
    if eid.startswith("mint_"):
        return "mint"
    if eid in ("arrow_boost", "double_shot"):
        return "arrow"
    if eid.startswith("slow") or "slow_mult" in effect:
        return "slow"
    if eid.startswith("cannon") or "splash_mult" in effect:
        return "cannon"
    if effect.get("free_arrow_layer"):
        return "arrow"
    return None


def _blueprint_weight_bonus(game: "GameSession") -> int:
    """前期、尚有未解锁塔种时提高蓝图权重。"""
    bonus = 0
    if game.level <= 6:
        bonus += 5
    if len(game.picked_upgrades) < 4:
        bonus += 4
    locked = sum(1 for t in _BLUEPRINT_TOWERS if t not in game.build_types)
    bonus += locked * 2
    return bonus


class UpgradeManager:
    def __init__(self, pool: list[dict]) -> None:
        self.pool = pool
        self.choices: list[dict] = []

    def roll_four(self, stats: RunStats, built_types: set[str], game: "GameSession | None" = None) -> list[dict]:
        available = []
        for card in self.pool:
            uid = card["id"]
            max_s = card.get("max_stacks", 99)
            if stats.upgrade_stacks.get(uid, 0) >= max_s:
                continue
            unlock = card["effect"].get("unlock_tower")
            if unlock in _BLUEPRINT_TOWERS and game:
                if unlock in stats.unlocked_towers or unlock in game.build_types:
                    continue
            req = required_tower_type(card)
            if req and game and req not in game.build_types:
                continue
            available.append(card)

        weighted: list[dict] = []
        for card in available:
            w = card.get("rarity", 1)
            tag = card.get("tag", "")
            unlock_tower = card["effect"].get("unlock_tower")
            if unlock_tower in _BLUEPRINT_TOWERS and game:
                w += _blueprint_weight_bonus(game)
            elif tag == "tower" and built_types:
                w += 1
            if unlock_tower in built_types:
                w += 2
            for _ in range(w):
                weighted.append(card)

        if len(weighted) < 4:
            weighted = available * 4 if available else self.pool[:4]

        picked: list[dict] = []
        bag = weighted[:]
        random.shuffle(bag)
        seen = set()
        for card in bag:
            if card["id"] in seen:
                continue
            seen.add(card["id"])
            picked.append(deepcopy(card))
            if len(picked) >= 4:
                break
        while len(picked) < 4 and available:
            c = random.choice(available)
            if c["id"] not in {p["id"] for p in picked}:
                picked.append(deepcopy(c))
        return picked[:4]

    def apply_choice(self, card: dict, stats: RunStats, game: "GameSession") -> None:
        uid = card["id"]
        stats.upgrade_stacks[uid] = stats.upgrade_stacks.get(uid, 0) + 1
        effect = card["effect"]
        stats.apply_effect(effect)

        if "instant_gold" in effect:
            game.gold += effect["instant_gold"]
        if "unlock_tower" in effect:
            t = effect["unlock_tower"]
            if t not in game.build_types:
                game.build_types.append(t)
        if effect.get("free_arrow_layer"):
            game.add_free_layer("arrow")

        if "base_hp_mult" in effect and effect["base_hp_mult"] != 0:
            old_max = game.base.max_hp
            game.base.recalc_max_hp(game)
            if old_max > 0:
                game.base.hp = min(
                    game.base.max_hp,
                    game.base.hp * (game.base.max_hp / old_max),
                )

        if "base_shield" in effect:
            game.base.shield += effect["base_shield"]

        if effect.get("base_pulse") or stats.base_pulse:
            game.base.pulse_enabled = True


TAG_LABELS = {
    "base": "基地",
    "tower": "防御塔",
    "global": "全局",
    "curse": "诅咒",
}


def find_upgrade(pool: list[dict], card_id: str) -> dict | None:
    for card in pool:
        if card["id"] == card_id:
            return card
    return None


# effect 字段 → 玩家可读的累计加成文案
_EFFECT_LABELS: dict[str, str] = {
    "base_hp_mult": "地基生命",
    "base_regen": "地基回复/秒",
    "base_thorns": "反伤/次",
    "base_aura_slow": "基地寒场减速",
    "base_shield": "护盾加成",
    "base_shield_regen": "护盾回复/秒",
    "kill_heal": "击杀回复/只",
    "tower_damage_mult": "全塔伤害",
    "tower_fire_rate_mult": "全塔攻速",
    "tower_range_mult": "全塔射程",
    "slow_mult": "寒塔减速",
    "splash_mult": "重炮爆炸范围",
    "double_shot_chance": "箭塔双发概率",
    "laser_ramp_mult": "激光蓄能",
    "laser_cap_mult": "激光伤害上限",
    "laser_range_mult": "激光射程",
    "laser_sweep_unlock": "激光广域扫射",
    "wind_fan_mult": "风塔扇形",
    "wind_knockback_mult": "风塔击退",
    "wind_rate_mult": "风塔攻速",
    "wind_range_mult": "风塔射程",
    "barracks_spawn_rate_mult": "兵营生成加速",
    "barracks_guard_hp_mult": "护卫生命",
    "barracks_guard_damage_mult": "护卫伤害",
    "barracks_guard_rate_mult": "护卫攻速",
    "barracks_max_guards_bonus": "护卫总上限",
    "barracks_spawn_count_bonus": "每次多召护卫",
    "mint_yield_mult": "赏金税",
    "mint_hoard_mult": "囤积红利",
    "mint_rate_mult": "钱塔结算加速",
    "mint_range_mult": "钱塔射程",
    "mint_cap_mult": "钱塔单次上限",
    "exp_mult": "获得经验",
    "gold_mult": "获得金币",
    "build_cost_mult": "建塔费用",
    "xp_need_mult": "升级经验需求",
    "enemy_hp_mult": "敌人生命",
    "max_layers": "塔层上限",
}

_PERCENT_KEYS = {
    "base_hp_mult",
    "base_aura_slow",
    "tower_damage_mult",
    "tower_fire_rate_mult",
    "tower_range_mult",
    "slow_mult",
    "splash_mult",
    "double_shot_chance",
    "laser_ramp_mult",
    "laser_cap_mult",
    "laser_range_mult",
    "wind_fan_mult",
    "wind_knockback_mult",
    "wind_rate_mult",
    "wind_range_mult",
    "barracks_spawn_rate_mult",
    "barracks_guard_hp_mult",
    "barracks_guard_damage_mult",
    "barracks_guard_rate_mult",
    "mint_yield_mult",
    "mint_hoard_mult",
    "mint_rate_mult",
    "mint_range_mult",
    "mint_cap_mult",
    "exp_mult",
    "gold_mult",
    "build_cost_mult",
    "xp_need_mult",
    "enemy_hp_mult",
}


def _fmt_num(key: str, value: float) -> str:
    if key in _PERCENT_KEYS:
        pct = int(round(value * 100))
        if key == "double_shot_chance":
            pct = min(100, max(0, pct))
        return f"{pct:+d}%"
    if isinstance(value, float) and value == int(value):
        return f"{int(value):+d}"
    return f"{value:+.1f}"


def _read_stat(stats: RunStats, key: str, sub: str | None = None) -> float:
    if key == "type_damage" and sub:
        return float(stats.type_damage.get(sub, 0))
    if key == "max_layers":
        return float(stats.max_layers_bonus)
    if hasattr(stats, key):
        val = getattr(stats, key)
        if isinstance(val, bool):
            return 1.0 if val else 0.0
        return float(val)
    return 0.0


def _preview_value_line(stats: RunStats, key: str, val) -> str | None:
    if key == "type_damage" and isinstance(val, dict):
        return None
    if not isinstance(val, (int, float)):
        return None
    cur = _read_stat(stats, key)
    aft = cur + float(val)
    if cur == 0 and aft == 0:
        return None
    if cur == 0:
        return _fmt_num(key, aft)
    if cur == aft:
        return _fmt_num(key, cur)
    return f"{_fmt_num(key, cur)} -> {_fmt_num(key, aft)}"


def _preview_effect_row(stats: RunStats, key: str, val) -> tuple[str, str | None] | None:
    if key in ("instant_gold", "unlock_tower", "free_arrow_layer"):
        return None
    if key == "base_pulse":
        return None
    if key == "laser_sweep_unlock" and val:
        return ("激光广域扫射", "已解锁")
    if key == "type_damage" and isinstance(val, dict):
        return None
    if not isinstance(val, (int, float)):
        return None
    label = _EFFECT_LABELS.get(key, key)
    value = _preview_value_line(stats, key, val)
    if value is None:
        return None
    return (label, value)


def _preview_effect_line(stats: RunStats, key: str, val) -> str | None:
    row = _preview_effect_row(stats, key, val)
    if row is None and key == "type_damage" and isinstance(val, dict):
        parts: list[str] = []
        for tid, delta in val.items():
            label = tower_damage_label(tid)
            cur = _read_stat(stats, key, tid)
            aft = cur + float(delta)
            parts.append(f"{label} {_fmt_num('tower_damage_mult', cur)} → {_fmt_num('tower_damage_mult', aft)}")
        return " · ".join(parts) if parts else None
    if row is None:
        return None
    desc, value = row
    if value is None:
        return desc
    return f"{desc} {value}"


def upgrade_pick_title(card: dict, stats: RunStats) -> str:
    """三选一卡片标题：选中后的叠层层级 + 名称。"""
    stacks = stats.upgrade_stacks.get(card["id"], 0)
    return f"Lv.{stacks + 1} {card['name']}"


def upgrade_pick_rows(card: dict, stats: RunStats) -> list[tuple[str, str | None]]:
    """三选一卡片正文：(描述, 数值)；数值为 None 时仅一行。"""
    effect = card.get("effect") or {}
    rows: list[tuple[str, str | None]] = []

    if effect.get("base_pulse"):
        from game.base_pulse import pulse_pick_rows

        rows.extend(pulse_pick_rows(stats))

    if "instant_gold" in effect:
        rows.append(("立即获得金币", f"+{int(effect['instant_gold'])}"))
    if "unlock_tower" in effect:
        tid = effect["unlock_tower"]
        name = tower_label(tid)
        rows.append(("解锁建造", name))
    if effect.get("free_arrow_layer"):
        rows.append(("免费叠层", "箭塔 +1"))

    if "type_damage" in effect and isinstance(effect["type_damage"], dict):
        for tid, delta in effect["type_damage"].items():
            label = tower_damage_label(tid)
            cur = _read_stat(stats, "type_damage", tid)
            aft = cur + float(delta)
            if cur == 0 and aft == 0:
                continue
            if cur == 0:
                rows.append((label, _fmt_num("tower_damage_mult", aft)))
            elif cur == aft:
                rows.append((label, _fmt_num("tower_damage_mult", cur)))
            else:
                rows.append(
                    (
                        label,
                        f"{_fmt_num('tower_damage_mult', cur)} -> {_fmt_num('tower_damage_mult', aft)}",
                    )
                )

    for key, val in effect.items():
        if key in ("instant_gold", "unlock_tower", "free_arrow_layer", "type_damage", "base_pulse"):
            continue
        row = _preview_effect_row(stats, key, val)
        if row:
            rows.append(row)
    return rows


def upgrade_pick_lines(card: dict, stats: RunStats) -> list[str]:
    lines: list[str] = []
    for desc, value in upgrade_pick_rows(card, stats):
        lines.append(desc)
        if value is not None:
            lines.append(value)
    return lines


def upgrade_detail_lines(
    card: dict, stacks: int = 0, stats: RunStats | None = None
) -> list[str]:
    lines = [card.get("desc", ""), ""]
    tag = TAG_LABELS.get(card.get("tag", ""), card.get("tag", "未知"))
    lines.append(f"类型: {tag}    稀有度: {card.get('rarity', '?')}")
    if stats is not None:
        lines.extend(upgrade_pick_lines(card, stats))
    else:
        max_s = card.get("max_stacks")
        if stacks > 0:
            lines.append(f"本局已叠: {stacks}" + (f" / 上限 {max_s}" if max_s else ""))
        elif max_s:
            lines.append(f"可叠加，上限 {max_s}")
        else:
            lines.append("可重复叠加")
        effect = card.get("effect") or {}
        if effect:
            lines.append("")
            lines.append("效果:")
            for key, val in effect.items():
                if isinstance(val, dict):
                    parts = ", ".join(f"{k}={v}" for k, v in val.items())
                    lines.append(f"  {key}: {parts}")
                elif isinstance(val, bool):
                    lines.append(f"  {key}: 是" if val else f"  {key}: 否")
                else:
                    lines.append(f"  {key}: {val}")
    return lines
