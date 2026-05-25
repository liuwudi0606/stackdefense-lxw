"""F1 调试菜单：Buff 按类别分组列表。"""

from __future__ import annotations

from dataclasses import dataclass

CATEGORY_ORDER = [
    "基地",
    "全塔通用",
    "箭塔",
    "寒塔",
    "重炮",
    "激光塔",
    "风塔",
    "兵营",
    "钱塔",
    "全局",
    "诅咒",
    "其它",
]

from game.tower_labels import TOWER_TYPE_LABELS

BUFF_HEADER_H = 32
BUFF_CARD_H = 28


@dataclass
class BuffListEntry:
    kind: str
    text: str = ""
    card: dict | None = None


def buff_category(card: dict) -> str:
    eid = card.get("id", "")
    effect = card.get("effect") or {}
    tag = card.get("tag", "")

    if tag == "curse":
        return "诅咒"
    if tag == "base":
        return "基地"

    unlock = effect.get("unlock_tower")
    if unlock:
        return TOWER_TYPE_LABELS.get(unlock, "其它")

    td = effect.get("type_damage")
    if isinstance(td, dict) and td:
        t = next(iter(td))
        return TOWER_TYPE_LABELS.get(t, "其它")

    if eid.startswith("laser_") or eid == "laser_sweep":
        return "激光塔"
    if eid.startswith("wind_"):
        return "风塔"
    if eid.startswith("barracks_"):
        return "兵营"
    if eid.startswith("mint_"):
        return "钱塔"
    if eid in ("arrow_boost", "double_shot"):
        return "箭塔"
    if eid.startswith("slow") or "slow_mult" in effect:
        return "寒塔"
    if eid.startswith("cannon") or "splash_mult" in effect:
        return "重炮"

    if tag == "tower" and any(
        k in effect
        for k in ("tower_damage_mult", "tower_fire_rate_mult", "tower_range_mult")
    ):
        return "全塔通用"

    if tag == "global" or effect.get("free_arrow_layer"):
        return "全局"

    return "其它"


def _buff_card_sort_key(card: dict) -> tuple[int, str]:
    """蓝图（解锁塔）排在对应分类的第一行。"""
    effect = card.get("effect") or {}
    if effect.get("unlock_tower") or "蓝图" in card.get("name", ""):
        return (0, card.get("name", ""))
    return (1, card.get("name", ""))


def build_buff_list_entries(pool: list[dict]) -> list[BuffListEntry]:
    buckets: dict[str, list[dict]] = {c: [] for c in CATEGORY_ORDER}
    for card in pool:
        if card.get("tag") == "base":
            continue
        cat = buff_category(card)
        buckets.setdefault(cat, []).append(card)

    entries: list[BuffListEntry] = []
    for cat in CATEGORY_ORDER:
        if cat == "基地":
            continue
        cards = buckets.get(cat) or []
        if not cards:
            continue
        entries.append(BuffListEntry("header", text=cat))
        for card in sorted(cards, key=_buff_card_sort_key):
            entries.append(BuffListEntry("card", card=card))
    return entries


def build_debug_buff_entries(
    run_pool: list[dict], base_pool: list[dict] | None = None
) -> list[BuffListEntry]:
    entries = build_buff_list_entries(run_pool)
    base_cards = list(base_pool or [])
    if not base_cards:
        return entries
    entries.append(BuffListEntry("header", text="基地强化(金币)"))
    for card in sorted(base_cards, key=_buff_card_sort_key):
        entries.append(BuffListEntry("card", card=card))
    return entries


def entry_height(entry: BuffListEntry) -> int:
    return BUFF_HEADER_H if entry.kind == "header" else BUFF_CARD_H
